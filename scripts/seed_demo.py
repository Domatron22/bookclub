# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Seed a local development database with demo content.

Dev-only helper for working on the UI: it fills every screen with enough data
that shelves, marquees, discussions and recaps actually have something to draw.
Not used by the app at runtime.

    .venv/bin/python scripts/seed_demo.py [--reset]

Logs in as `you` — the script prints the cookie value to set.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Book,
    Club,
    Discussion,
    DiscussionComment,
    DiscussionPost,
    DiscussionPostLike,
    Meeting,
    MeetingRSVP,
    MeetingSchedule,
    Member,
    MemberBookCompletion,
    MemberBookProgress,
    Rating,
    ReviewComment,
    ReviewLike,
    User,
)

NOW = datetime(2026, 8, 25, 12, 0, 0)

# Finished books, newest first — the club shelf.
SHELF = [
    ("Klara and the Sun", "Kazuo Ishiguro", 320, 1,
     "An artificial friend narrates a story about love, faith, and what it means to be seen. "
     "The book that started our summer of big feelings."),
    ("Project Hail Mary", "Andy Weir", 476, 2,
     "A lone astronaut, an impossible problem, and the most charming first contact in years. "
     "We could not stop talking about Rocky."),
    ("Beloved", "Toni Morrison", 324, 3,
     "Haunting in every sense. Our longest, most careful discussion to date — we needed two "
     "meetings for it."),
    ("The Hobbit", "J.R.R. Tolkien", 310, 4,
     "A palate cleanser and a comfort read. There and back again, with snacks."),
    ("Educated", "Tara Westover", 352, 5,
     "A memoir that sparked our most personal conversation about family, memory, and "
     "self-invention."),
    ("Dune", "Frank Herbert", 412, 6,
     "The one that split the room. Half of us wanted maps; the other half wanted a spice ration."),
]

SHORTLIST = [
    ("Piranesi", "Susanna Clarke", 272),
    ("Tomorrow, and Tomorrow, and Tomorrow", "Gabrielle Zevin", 401),
    ("The Left Hand of Darkness", "Ursula K. Le Guin", 304),
    ("Circe", "Madeline Miller", 393),
]

REVIEWS = [
    ("Nora", 5, "Powers writes trees the way most novelists write people — with backstory, "
                "motive, grief. The multi-strand structure asks patience but pays it back tenfold."),
    ("You", 4, "Gorgeous and a little overwhelming. Docked one star only because a couple of the "
               "threads lost me — but the canopy chapters are unforgettable."),
    ("Priya", 5, "Cried on a train reading the last section. No notes."),
    ("Theo", 5, "A memoir that reads like a thriller. We talked about it for two meetings straight."),
    ("Sam", 4, "Bring a map and a snack. Dense, strange, and completely worth the climb."),
]

# One standout review per shelf title, so the club's review marquee reads as a
# real spread of opinions rather than the same paragraph repeated.
BOOK_REVIEWS = {
    "Klara and the Sun": [
        ("Nora", 5, "Quietly devastating. Ishiguro writes hope like no one else working today."),
        ("Theo", 4, "The narration is the whole trick, and it works. I kept forgetting who was telling me this."),
        ("Priya", 4, "Slow in the middle, but the last forty pages rearranged my week."),
    ],
    "Project Hail Mary": [
        ("Nora", 5, "The most charming first contact in years — I finished it in a single greedy weekend."),
        ("Sam", 5, "Rocky is the best fictional friendship of the decade. Fight me, gently, over wine."),
        ("You", 4, "Cheerfully ridiculous science and I did not care even slightly."),
    ],
    "Beloved": [
        ("Priya", 5, "Cried on a train reading the last section. No notes. A book that rearranges you."),
        ("Nora", 5, "We needed two meetings and I'd happily have given it three."),
        ("Theo", 4, "Hard going, and every page earns it."),
    ],
    "The Hobbit": [
        ("Sam", 4, "A comfort read with excellent snacks. There and back again indeed."),
        ("You", 4, "The palate cleanser we badly needed after Beloved."),
        ("Theo", 3, "Charming, slight, and over before I'd settled in."),
    ],
    "Educated": [
        ("Theo", 5, "A memoir that reads like a thriller. We talked about it for two meetings straight."),
        ("Priya", 5, "The chapter on the junkyard is one of the most tense things I've ever read."),
        ("Nora", 4, "Our most personal discussion to date, by some distance."),
    ],
    "Dune": [
        ("Sam", 4, "Bring a map and a snack. Dense, strange, and completely worth the climb."),
        ("Nora", 4, "A defence of the slow middle: the desert is supposed to feel endless."),
        ("You", 3, "Half of us wanted maps, the other half wanted a spice ration. I wanted both."),
    ],
}


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        if db.query(User).first():
            print("Database already has users — pass --reset to start clean.")
            return

        users = {}
        for name, display in [
            ("you", "You"), ("nora", "Nora"), ("theo", "Theo"),
            ("priya", "Priya"), ("sam", "Sam"),
        ]:
            u = User(
                username=name,
                account_secret=f"demo-secret-{name}",
                display_name=display,
                created_at=NOW - timedelta(days=240),
                last_seen_at=NOW,
                bio="Slow reader, fast opinions. Here for the endings that don't resolve."
                    if name == "you" else f"{display} reads mostly at night.",
                favorite_genre="Literary fiction",
                favorite_book="The Left Hand of Darkness",
                favorite_author="Ursula K. Le Guin",
            )
            db.add(u)
            users[display] = u
        db.commit()

        clubs_spec = [
            ("The Nightstand Society", "MOONLIT", "voting",
             "A cozy corner for slow readers. We meet monthly, bring snacks, and argue kindly "
             "about endings."),
            ("Sci-Fi & Chill", "WARPX", "random",
             "Speculative fiction, big ideas, and zero gatekeeping. Wormholes optional, snacks "
             "mandatory."),
            ("Mystery Mondays", "NOIR7", "voting",
             "We solve it before the detective does. Whodunits, locked rooms, and the occasional "
             "red herring."),
        ]

        primary_club = None
        for idx, (name, code, method, desc) in enumerate(clubs_spec):
            club = Club(
                name=name, code=code, description=desc,
                created_at=NOW - timedelta(days=240 - idx * 60),
                veto_enabled=True, veto_percentage=50,
                book_selection_method=method, voting_percentage=60,
                # Vote counts hidden on the voting club so the "hidden tallies"
                # callout is visible; shown on one club to exercise both paths.
                votes_visible=(idx == 2),
                is_public=(idx != 2),
                feature_progress=True,
                feature_recap=True,
            )
            db.add(club)
            db.commit()
            db.refresh(club)

            roster = ["Nora", "You", "Theo", "Priya", "Sam"][: 5 - idx]
            members = {}
            for i, display in enumerate(roster):
                m = Member(
                    club_id=club.id,
                    user_id=users[display].id,
                    display_name=display,
                    is_admin=(display == "Nora" or (display == "You" and idx == 0)),
                    joined_at=NOW - timedelta(days=230 - idx * 60),
                    profile_visible=(idx != 2),
                )
                db.add(m)
                members[display] = m
            db.commit()

            if idx == 0:
                primary_club = (club, members)

            # The random-selection club is deliberately left between books, so
            # the "choose the next read" reel and the club's empty currently-
            # reading state are both reachable in the demo data.
            between_books = (method == "random")

            # Currently reading
            current = Book(
                club_id=club.id,
                title=["The Overstory", "The Left Hand of Darkness", "Piranesi"][idx],
                author=["Richard Powers", "Ursula K. Le Guin", "Susanna Clarke"][idx],
                description="Nine strangers, each summoned in a different way by trees, are "
                            "brought together for the last stand of the continent's few "
                            "remaining acres of virgin forest.",
                page_count=[512, 304, 272][idx],
                status="completed" if between_books else "reading",
                suggested_by=members["Nora"].id,
                selected_at=NOW - timedelta(days=30),
                completed_at=NOW - timedelta(days=2) if between_books else None,
            )
            db.add(current)

            # Shelf
            for title, author, pages, months_ago, blurb in SHELF[: 6 - idx * 2]:
                db.add(Book(
                    club_id=club.id, title=title, author=author, description=blurb,
                    page_count=pages, status="completed",
                    suggested_by=members[roster[months_ago % len(roster)]].id,
                    selected_at=NOW - timedelta(days=30 * months_ago + 28),
                    completed_at=NOW - timedelta(days=30 * months_ago),
                ))

            # Shortlist
            for title, author, pages in SHORTLIST:
                db.add(Book(
                    club_id=club.id, title=title, author=author, page_count=pages,
                    description=f"Suggested for the next round in {name}.",
                    status="suggested",
                    suggested_by=members[roster[len(title) % len(roster)]].id,
                    suggested_at=NOW - timedelta(days=12),
                ))
            db.commit()

            # Meeting schedule + meetings
            # "You" hosts the primary club so host-only screens (schedule a
            # meeting, transfer host) are reachable while working on the UI.
            db.add(MeetingSchedule(
                club_id=club.id,
                current_host_id=members["You"].id if idx == 0 else members["Nora"].id,
                recurrence_pattern="monthly", recurrence_details="Every 4th Tuesday",
                default_duration_minutes=120, is_active=True,
            ))
            upcoming = Meeting(
                club_id=club.id, host_id=members["Nora"].id,
                title=(f"{current.title} — chapters 1–12" if not between_books
                       else f"{name} — picking our next read"),
                meeting_datetime=NOW + timedelta(days=3, hours=7),
                duration_minutes=120, location="Nora's place",
                description="Bring wine and hot takes — we'll cover the first section and that "
                            "framing device everyone has feelings about.",
                status="scheduled",
            )
            db.add(upcoming)
            db.add(Meeting(
                club_id=club.id, host_id=members[roster[0]].id,
                title="Klara and the Sun — finale",
                meeting_datetime=NOW - timedelta(days=32),
                duration_minutes=120, location="The Fox & Fable pub",
                status="completed", completed_at=NOW - timedelta(days=32),
            ))
            db.commit()
            db.refresh(upcoming)

            for display, status, bringing in [
                ("Nora", "yes", "Two bottles of Syrah + the discussion questions"),
                ("Theo", "yes", "Homemade focaccia"),
                ("You", "maybe", ""),
                ("Priya", "yes", "A serious cheese board"),
            ]:
                if display in members:
                    db.add(MeetingRSVP(
                        meeting_id=upcoming.id, member_id=members[display].id,
                        status=status, bringing=bringing,
                        notes="Might be 10 minutes late." if display == "You" else "",
                    ))
            db.commit()

        # ---- Rich content on the primary club's shelf ----
        club, members = primary_club
        shelf_books = db.query(Book).filter(
            Book.club_id == club.id, Book.status == "completed"
        ).all()
        current = db.query(Book).filter(
            Book.club_id == club.id, Book.status == "reading"
        ).first()

        for book in shelf_books + [current]:
            for i, (who, stars, text) in enumerate(BOOK_REVIEWS.get(book.title, REVIEWS)):
                if who not in members:
                    continue
                r = Rating(
                    book_id=book.id, member_id=members[who].id,
                    rating=stars, review=text,
                    created_at=NOW - timedelta(days=10 - i),
                    updated_at=NOW - timedelta(days=10 - i),
                )
                db.add(r)
                db.commit()
                db.refresh(r)
                if i == 0:
                    db.add(ReviewLike(rating_id=r.id, member_id=members["Theo"].id))
                    db.add(ReviewComment(
                        rating_id=r.id, member_id=members["Theo"].id,
                        content="The patience point is real. First 100 pages I almost quit; "
                                "so glad I didn't.",
                    ))
            db.commit()

        for book in shelf_books[:3]:
            for display in ["Nora", "You", "Priya"]:
                db.add(MemberBookCompletion(
                    member_id=members[display].id, book_id=book.id,
                    completed_at=book.completed_at or NOW,
                ))
        db.commit()

        # Reading positions on the current book — a spread so the progress
        # summary reads "2 of 5 finished" with a mix of bars.
        for display, page in [("Nora", 512), ("You", 210), ("Theo", 384),
                              ("Priya", 512), ("Sam", 96)]:
            if display in members:
                db.add(MemberBookProgress(
                    member_id=members[display].id, book_id=current.id,
                    page=page, updated_at=NOW - timedelta(days=1),
                ))
        db.commit()

        # Discussions on the current book. Each gets its own opening post and
        # engagement so the recap's "most-talked-about" list has real variety.
        for title, days, opener, likers in [
            ("That ending — did it earn it?", 13,
             "Okay, opening this up: I loved how the first section slowly reframes what you think "
             "the book is about. No spoilers in this top post — reply with your section-by-section "
             "reactions.",
             ["Theo", "Priya", "Sam"]),
            ("The framing device: clever or a crutch?", 16,
             "Genuine question: does the structure earn itself, or is it scaffolding the story "
             "leans on because the middle doesn't hold? I flip-flopped twice on the train home.",
             ["Priya", "Sam"]),
            ("Favorite passage so far (no spoilers past ch. 12)", 20,
             "Drop your favourite sentence. Mine is the one about the light coming through the "
             "canopy — I read it four times and then read it out loud to someone who hadn't asked.",
             ["Theo"]),
        ]:
            d = Discussion(book_id=current.id, title=title,
                           created_at=NOW - timedelta(days=days))
            db.add(d)
            db.commit()
            db.refresh(d)

            p1 = DiscussionPost(
                discussion_id=d.id, author_id=members["Nora"].id, is_spoiler=False,
                created_at=NOW - timedelta(days=days),
                content=opener,
            )
            p2 = DiscussionPost(
                discussion_id=d.id, author_id=members["Theo"].id, is_spoiler=True,
                created_at=NOW - timedelta(days=days - 1),
                content="Full-book spoiler: the reveal that the narrator was unreliable the whole "
                        "time recontextualizes every earlier chapter — especially the garden scene.",
            )
            db.add_all([p1, p2])
            db.commit()
            db.refresh(p1)
            db.refresh(p2)

            for who in likers:
                db.add(DiscussionPostLike(post_id=p1.id, member_id=members[who].id))
            c1 = DiscussionComment(
                post_id=p1.id, author_id=members["Theo"].id, is_spoiler=False,
                content="The pacing in the middle third is doing a LOT of quiet work. "
                        "I didn't notice until the payoff.",
            )
            db.add(c1)
            db.commit()
            db.refresh(c1)
            db.add(DiscussionComment(
                post_id=p1.id, parent_comment_id=c1.id, author_id=members["Priya"].id,
                is_spoiler=False, content="Agreed — second read, it's all foreshadowing.",
            ))
            db.add(DiscussionComment(
                post_id=p2.id, author_id=members["You"].id, is_spoiler=True,
                content="I had to put the book down for a full day after that. The garden scene "
                        "hit completely differently on reread.",
            ))
            db.commit()

        you = db.query(User).filter(User.username == "you").first()
        print("Seeded demo data.")
        # Identity lives in the signed session cookie now, so there is no cookie
        # to hand-set — sign in through the form like a real user would.
        print(f"  Sign in as:  username 'you'  /  secret 'demo-secret-you'")
        print(f"  Primary club: {club.name} (/clubs/{club.code})")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = ap.parse_args()

    # The Docker container runs as APP_UID:APP_GID (4001 by default) and mounts
    # ./data read-write while the rest of its filesystem is read-only. Creating
    # this directory here gives it *our* ownership, which the container then
    # can't write to — so say so rather than leaving a confusing SQLite error.
    if not os.path.isdir("data"):
        os.makedirs("data", exist_ok=True)
        print(
            "Created ./data owned by this user. If you also run the Docker\n"
            "container, either run `make init` (chowns it to 4001:4001) or start\n"
            "compose as yourself:\n"
            f"  APP_UID={os.getuid()} APP_GID={os.getgid()} docker compose up -d\n"
        )
    if args.reset:
        reset_database()
    else:
        Base.metadata.create_all(bind=engine)
    seed()
