# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Year-in-books aggregation, for a single club or across all of a user's clubs.

Everything is computed at query time from existing rows — there is no recap
table. A "year" is the calendar year a book was finished in, or a post was
written in.
"""
from collections import Counter
from datetime import datetime

from .models import Book, DiscussionPost, MemberBookCompletion, Rating


def _avg(scores):
    return round(sum(scores) / len(scores), 1) if scores else None


def _rank_books(books, limit=3):
    """Top books by average rating, richest first, with a short note."""
    scored = []
    for book in books:
        scores = [r.rating for r in book.ratings]
        if not scores:
            continue
        best = max(book.ratings, key=lambda r: r.rating)
        scored.append({
            "book": book,
            "rating": _avg(scores),
            "reviews": len(scores),
            "note": (best.review or "").strip(),
        })
    scored.sort(key=lambda x: (x["rating"], x["reviews"]), reverse=True)
    return scored[:limit]


def _rank_posts(posts, limit=3):
    """Top discussion posts by engagement (likes + replies)."""
    scored = []
    for post in posts:
        likes = len(post.likes)
        replies = len(post.comments)
        if likes + replies == 0:
            continue
        scored.append({
            "post": post,
            "author": post.author.display_name if post.author else "Someone",
            "book": post.discussion.book.title if post.discussion and post.discussion.book else "",
            "discussion_id": post.discussion_id,
            "snippet": (post.content or "").strip(),
            "likes": likes,
            "replies": replies,
        })
    scored.sort(key=lambda x: (x["likes"] + x["replies"], x["likes"]), reverse=True)
    return scored[:limit]


def _finished_in_year(books, year):
    return [
        b for b in books
        if b.status == "completed" and b.completed_at and b.completed_at.year == year
    ]


def _year_bounds(year):
    """Half-open [start, end) for a calendar year, so the database can use an
    index instead of computing a year per row."""
    return datetime(year, 1, 1), datetime(year + 1, 1, 1)


def club_recap(club, year=None) -> dict:
    """The club's reading year."""
    year = year or datetime.utcnow().year
    finished = _finished_in_year(club.books, year)

    posts = [
        p for b in club.books for d in b.discussions for p in d.posts
        if p.created_at and p.created_at.year == year
    ]
    ratings = [r for b in finished for r in b.ratings]
    meetings = [
        m for m in club.meetings
        if m.meeting_datetime and m.meeting_datetime.year == year and m.status == "completed"
    ]
    pages = sum(b.page_count or 0 for b in finished)

    # Most active reader by posts written this year.
    author_counts = Counter(p.author.display_name for p in posts if p.author)
    top_reader, top_reader_posts = (author_counts.most_common(1) or [(None, 0)])[0]

    longest = max(finished, key=lambda b: b.page_count or 0, default=None)
    top_books = _rank_books(finished)

    return {
        "year": year,
        "scope": "club",
        "title": club.name,
        "headline": f"{year}, in books.",
        "books_read": len(finished),
        "stats": [
            (len(finished), "Books read"),
            (f"{pages:,}" if pages else "—", "Pages turned"),
            (len(meetings), "Meetings held"),
            (_avg([r.rating for r in ratings]) or "—", "Avg. rating"),
        ],
        "highlights": [
            ("fa-trophy", "Top rated", top_books[0]["book"].title if top_books else "—",
             f"{top_books[0]['rating']} average" if top_books else "No ratings yet"),
            ("fa-fire", "Most active reader", top_reader or "—",
             f"{top_reader_posts} posts" if top_reader else "No posts yet"),
            ("fa-book-bookmark", "Longest read",
             longest.title if longest and longest.page_count else "—",
             f"{longest.page_count} pages" if longest and longest.page_count else "Page counts not set"),
            ("fa-users", "Members", str(len(club.members)),
             "reading together"),
        ],
        "top_books": top_books,
        "top_posts": _rank_posts(posts),
        "shelf": finished,
    }


def personal_recap(user, db, year=None) -> dict:
    """The user's reading year across every club they're in."""
    year = year or datetime.utcnow().year
    member_ids = [m.id for m in user.members]
    clubs = [m.club for m in user.members if m.club]
    start, end = _year_bounds(year)

    if not member_ids:
        finished, my_ratings_this_year, my_posts = [], [], []
    else:
        # Books this user personally marked finished this year.
        #
        # `distinct` is belt-and-braces rather than a fix: a Book belongs to
        # one club, a user holds one Member row per club, and completions are
        # unique on (member_id, book_id), so the join cannot fan out today. It
        # costs nothing and keeps the count right if any of those ever change.
        finished = (
            db.query(Book)
            .join(MemberBookCompletion, MemberBookCompletion.book_id == Book.id)
            .filter(
                MemberBookCompletion.member_id.in_(member_ids),
                MemberBookCompletion.completed_at >= start,
                MemberBookCompletion.completed_at < end,
            )
            .distinct()
            .all()
        )

        my_ratings_this_year = (
            db.query(Rating)
            .filter(
                Rating.member_id.in_(member_ids),
                Rating.created_at >= start,
                Rating.created_at < end,
            )
            .all()
        )

        my_posts = (
            db.query(DiscussionPost)
            .filter(
                DiscussionPost.author_id.in_(member_ids),
                DiscussionPost.created_at >= start,
                DiscussionPost.created_at < end,
            )
            .all()
        )

    pages = sum(b.page_count or 0 for b in finished)

    # Which club did most of the reading happen with?
    club_counts = Counter()
    for book in finished:
        club_counts[book.club_id] += 1
    top_club_id, top_club_books = (club_counts.most_common(1) or [(None, 0)])[0]
    top_club = next((c for c in clubs if c.id == top_club_id), None)

    rated_best = sorted(my_ratings_this_year, key=lambda r: r.rating, reverse=True)
    genre = user.favorite_genre or "—"

    return {
        "year": year,
        "scope": "personal",
        "title": user.display_name or user.username,
        "headline": f"Your {year}, in books.",
        "books_read": len(finished),
        "stats": [
            (len(finished), "Books read"),
            (f"{pages:,}" if pages else "—", "Pages turned"),
            (len(clubs), "Clubs"),
            (_avg([r.rating for r in my_ratings_this_year]) or "—", "Avg. rating"),
        ],
        "highlights": [
            ("fa-trophy", "Your top book",
             rated_best[0].book.title if rated_best else "—",
             f"You rated it {rated_best[0].rating} stars" if rated_best else "No ratings yet"),
            ("fa-users", "Most-read-with club", top_club.name if top_club else "—",
             f"{top_club_books} books together" if top_club else "No finished books yet"),
            ("fa-comments", "Posts written", str(len(my_posts)),
             "across your clubs"),
            ("fa-theater-masks", "Your top genre", genre,
             "from your profile" if user.favorite_genre else "Set one in settings"),
        ],
        "top_books": _rank_books(finished),
        "top_posts": _rank_posts(my_posts),
        "shelf": finished,
        "clubs": clubs,
    }
