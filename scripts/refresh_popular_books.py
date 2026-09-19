# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Refresh the pool of covers the landing hero rotates through.

Asks Open Library for its best-rated books, checks that each cover image really
loads, and writes `app/popular_books.json`.

    .venv/bin/python scripts/refresh_popular_books.py [--limit N] [--no-verify]

Nothing calls this at runtime — the landing page reads the file, and the
committed one keeps working until you re-run this.
"""
import argparse
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from app import open_library  # noqa: E402
from app.popular_books import DATA_FILE  # noqa: E402

VERIFY_PAUSE = 0.25
HEADERS = {"User-Agent": "Coverbound/1.0 (self-hosted book club)"}


def cover_loads(url: str) -> bool:
    """True if the cover really resolves — the hero should never get a dud."""
    try:
        r = requests.get(url + "?default=false", headers=HEADERS,
                         timeout=15, stream=True)
        ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")
        r.close()
        return ok
    except requests.RequestException:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=open_library.TOP_RATED_LIMIT,
                        help="how many books to pull (default 100)")
    parser.add_argument("--min-votes", type=int, default=open_library.TOP_RATED_MIN_VOTES,
                        help="minimum ratings a book needs to qualify (default 150)")
    parser.add_argument("--subject", default=open_library.TOP_RATED_SUBJECT,
                        help="narrow the pool to a subject (default 'fiction'; "
                             "pass '' for no filter)")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip checking that each cover image loads")
    args = parser.parse_args()

    scope = f" in '{args.subject}'" if args.subject else ""
    print(f"Fetching the top {args.limit} books{scope} "
          f"with at least {args.min_votes} ratings…")
    books = open_library.top_rated(limit=args.limit, min_votes=args.min_votes,
                                   subject=args.subject)
    if not books:
        print("Open Library returned nothing — leaving the existing file alone.",
              file=sys.stderr)
        return 1
    print(f"  got {len(books)} with cover art.")

    if not args.no_verify:
        print("Verifying each cover loads…")
        kept, dropped = [], []
        for i, b in enumerate(books):
            if i:
                time.sleep(VERIFY_PAUSE)
            (kept if cover_loads(b["cover_url"]) else dropped).append(b)
        for b in dropped:
            print(f"  dropped (cover did not load): {b['title']}")
        books = kept

    payload = {
        "generated": date.today().isoformat(),
        "source": (f"Open Library search, sort=rating, "
                   f"ratings_count>={args.min_votes}"
                   + (f", subject:{args.subject}" if args.subject else "")),
        "books": books,
    }
    DATA_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"\nWrote {len(books)} books to {DATA_FILE}")
    print("Top of the pool:")
    for b in books[:5]:
        print(f"  {b['rating']}  ({b['votes']} ratings)  {b['title']} — {b['author']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
