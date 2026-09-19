# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Fetch cover art for books that don't have any yet.

Walks books with no `cover_url`, asks Open Library, and saves what it finds.
Books that already have one are skipped, so it is safe to re-run — which is
also how you pick up anything a slow response missed.

    .venv/bin/python scripts/backfill_covers.py [--dry-run] [--limit N]

Requests are paced one per second, and a book it can't match keeps its
placeholder.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Book  # noqa: E402
from app import open_library  # noqa: E402

PAUSE_SECONDS = 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be filled in without saving")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after N books (0 = no limit)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Book).filter(
            (Book.cover_url == None) | (Book.cover_url == "")  # noqa: E711
        ).order_by(Book.id)
        if args.limit:
            query = query.limit(args.limit)
        books = query.all()

        if not books:
            print("Every book already has a cover.")
            return 0

        print(f"{len(books)} book(s) without cover art.\n")
        found = 0
        for i, book in enumerate(books):
            if i:
                time.sleep(PAUSE_SECONDS)
            result = open_library.lookup_cover(book.title, book.author)
            if not result:
                print(f"  ·  {book.title} — {book.author}: no cover found")
                continue

            found += 1
            print(f"  ✓  {book.title} — {book.author}: {result['cover_url']}")
            if not args.dry_run:
                book.cover_url = result["cover_url"]
                if not book.open_library_id:
                    book.open_library_id = result["open_library_id"]

        if args.dry_run:
            print(f"\nDry run: {found}/{len(books)} would get cover art.")
        else:
            db.commit()
            print(f"\nSaved cover art for {found}/{len(books)} book(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
