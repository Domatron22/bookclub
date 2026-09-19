# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""The pool of book covers the landing hero rotates through.

Three are drawn at random per page load, so the hero reads as "books people
rate highly" rather than an endorsement of three titles. The pool is a file on
disk, refreshed by `scripts/refresh_popular_books.py` and never fetched during
a request — the landing page must not wait on a third party. Missing or
unreadable, it falls back to the curated covers below.
"""
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent / "popular_books.json"

# Hand-picked to compose: a layered landscape, gold-on-black, and burgundy.
FALLBACK_BOOKS = [
    {"title": "The Overstory", "author": "Richard Powers",
     "cover_url": "https://covers.openlibrary.org/b/id/8758252-M.jpg"},
    {"title": "Circe", "author": "Madeline Miller",
     "cover_url": "https://covers.openlibrary.org/b/id/8739376-M.jpg"},
    {"title": "Beloved", "author": "Toni Morrison",
     "cover_url": "https://covers.openlibrary.org/b/id/15248310-M.jpg"},
]

_books = None  # module-level cache; the file is read once per process


def _load() -> "list[dict]":
    global _books
    if _books is None:
        try:
            payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            _books = [b for b in payload.get("books", []) if b.get("cover_url")]
        except (OSError, ValueError, AttributeError) as exc:
            logger.info("No usable %s (%s); hero falls back to curated covers.",
                        DATA_FILE.name, exc)
            _books = []
        if not _books:
            _books = FALLBACK_BOOKS
    return _books


def hero_picks(count: int = 3) -> "list[dict]":
    """`count` books at random, reshuffled on every call.

    One book per author — the pool leans on series, and a hero showing two
    volumes of the same one reads as a bug. Repeats are allowed only if the
    pool is too small or lopsided to do better.
    """
    books = _load()
    if len(books) <= count:
        return list(books)

    shuffled = random.sample(books, len(books))
    picked, seen = [], set()
    for book in shuffled:
        author = (book.get("author") or "").casefold()
        if author and author in seen:
            continue
        seen.add(author)
        picked.append(book)
        if len(picked) == count:
            return picked

    # Not enough distinct authors — top up rather than return a short hero.
    for book in shuffled:
        if len(picked) == count:
            break
        if book not in picked:
            picked.append(book)
    return picked
