# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Book metadata lookup via the Open Library search API.

No API key required. Every call is best-effort: `search` returns
`(results, failed)` so the UI can fall back to manual entry rather than
presenting an empty list as "no matches".
"""
import logging
from collections import Counter

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://openlibrary.org/search.json"
TIMEOUT_SECONDS = 6
MAX_RESULTS = 12

# Only ask for the fields we render, which keeps the response small.
FIELDS = "key,title,author_name,first_publish_year,number_of_pages_median,cover_i,ratings_average"

# Search also needs the subtitle. Series are often catalogued with the series
# name as the title and the volume in the subtitle — every Awaken Online book
# is titled "Awaken Online" — so the title alone can't tell them apart.
# `editions.*` describes the edition that best matched the query, the only
# clue left when a work is missing its own subtitle.
SEARCH_FIELDS = FIELDS + ",subtitle,editions,editions.subtitle,editions.cover_i"


def _full_title(doc: dict, ambiguous: bool, query: str) -> "tuple[str, dict | None]":
    """The work's title with its subtitle, e.g. "Awaken Online: Hellion".

    Returns `(title, edition)`, where `edition` is set when the subtitle was
    borrowed from the matched edition, so the caller can take that edition's
    cover too. Open Library sometimes merges a whole series into one work, and
    the work's own cover would then belong to a different volume.

    Borrowing only happens when another result shares this title
    (`ambiguous`) or the query names the subtitle — "awaken online catharsis".
    Edition subtitles are noisy ("Dune Chronicles, Book 2"), so they are used
    only where something is needed to tell results apart.
    """
    title = (doc.get("title") or "").strip()
    subtitle = (doc.get("subtitle") or "").strip()
    edition = None
    if not subtitle:
        editions = (doc.get("editions") or {}).get("docs") or []
        candidate = (editions[0].get("subtitle") or "").strip() if editions else ""
        if candidate and (ambiguous or _normalize(candidate) in _normalize(query)):
            edition = editions[0]
            subtitle = candidate
    if subtitle and _normalize(subtitle) not in _normalize(title):
        return f"{title}: {subtitle}", edition
    return title, None


def search(query: str) -> "tuple[list[dict], bool]":
    """Return (results, failed). `failed` distinguishes an error from no matches."""
    try:
        response = requests.get(
            SEARCH_URL,
            params={"q": query, "fields": SEARCH_FIELDS, "limit": MAX_RESULTS},
            headers={"User-Agent": "Coverbound/1.0 (self-hosted book club)"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Open Library search failed for %r: %s", query, exc)
        return [], True

    docs = payload.get("docs", [])
    title_counts = Counter(_normalize(d.get("title")) for d in docs)

    results = []
    for doc in docs:
        if not (doc.get("title") or "").strip():
            continue
        title, edition = _full_title(doc, ambiguous=title_counts[_normalize(doc["title"])] > 1,
                                     query=query)
        cover_id = (edition or {}).get("cover_i") or doc.get("cover_i")
        authors = doc.get("author_name") or []
        rating = doc.get("ratings_average")
        results.append({
            "title": title[:300],
            "author": (authors[0] if authors else "Unknown")[:200],
            "year": doc.get("first_publish_year"),
            "pages": doc.get("number_of_pages_median"),
            "rating": round(rating, 1) if rating else None,
            # e.g. "/works/OL27448W" → "OL27448W"
            "open_library_id": (doc.get("key") or "").rsplit("/", 1)[-1][:40] or None,
            "cover_url": (
                f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                if cover_id else None
            ),
        })
    return results, False


def _normalize(text: str) -> str:
    """Loose key for comparing titles: case, punctuation and spacing ignored."""
    return "".join(c for c in (text or "").lower() if c.isalnum())


def lookup_cover(title: str, author: str, timeout: float = TIMEOUT_SECONDS) -> "dict | None":
    """Find cover art from a title and author, for books typed in by hand.

    Uses the structured `title`/`author` params rather than free-text `q`, which
    is markedly more precise for a known title. Callers that nothing is waiting
    on — a background task, a backfill run — can raise `timeout`.

    Returns `{"cover_url", "open_library_id"}`, or None on any failure, so the
    caller simply keeps the placeholder cover.
    """
    if not (title or "").strip():
        return None

    params = {"title": title.strip(), "fields": FIELDS, "limit": 5}
    if (author or "").strip():
        params["author"] = author.strip()

    try:
        response = requests.get(
            SEARCH_URL,
            params=params,
            headers={"User-Agent": "Coverbound/1.0 (self-hosted book club)"},
            timeout=timeout,
        )
        response.raise_for_status()
        docs = response.json().get("docs", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Open Library cover lookup failed for %r: %s", title, exc)
        return None

    wanted = _normalize(title)
    for doc in docs:
        if not doc.get("cover_i"):
            continue
        # Guard against a loose relevance match hanging the wrong art on the
        # book. Prefix rather than equality so "Dune" still matches an edition
        # catalogued as "Dune: 50th Anniversary Edition".
        found = _normalize(doc.get("title"))
        if not (found.startswith(wanted) or wanted.startswith(found)):
            continue
        return {
            "cover_url": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg",
            "open_library_id": (doc.get("key") or "").rsplit("/", 1)[-1][:40] or None,
        }
    return None


# A bare `sort=rating` surfaces obscure titles carried by a handful of votes,
# so require a floor of ratings first.
TOP_RATED_MIN_VOTES = 150
TOP_RATED_LIMIT = 100
# Unfiltered, "best rated" mixes novels with business and self-help titles —
# accurate, but off-key on a book club's front page.
TOP_RATED_SUBJECT = "fiction"


def top_rated(limit: int = TOP_RATED_LIMIT, min_votes: int = TOP_RATED_MIN_VOTES,
              subject: str = TOP_RATED_SUBJECT, timeout: float = 30) -> "list[dict]":
    """Best-rated books that clear a minimum number of ratings.

    `subject` narrows the pool (empty string for no filter). For the refresh
    script, not the request path. Only books with cover art are returned.
    """
    query = f"ratings_count:[{min_votes} TO *]"
    if subject:
        query += f" AND subject:{subject}"
    try:
        response = requests.get(
            SEARCH_URL,
            params={
                "q": query,
                "sort": "rating",
                "fields": "title,author_name,ratings_average,ratings_count,cover_i",
                "limit": limit,
            },
            headers={"User-Agent": "Coverbound/1.0 (self-hosted book club)"},
            timeout=timeout,
        )
        response.raise_for_status()
        docs = response.json().get("docs", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Open Library top-rated fetch failed: %s", exc)
        return []

    books = []
    for doc in docs:
        title = (doc.get("title") or "").strip()
        if not (title and doc.get("cover_i")):
            continue
        authors = doc.get("author_name") or []
        books.append({
            "title": title[:300],
            "author": (authors[0] if authors else "Unknown")[:200],
            "cover_url": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg",
            "rating": round(doc.get("ratings_average") or 0, 2),
            "votes": doc.get("ratings_count"),
        })
    return books
