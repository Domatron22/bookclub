# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Deleting an account, and leaving a club.

The contract, in both cases:

* everything the member personally contributed goes with them — posts, votes,
  ratings, progress, RSVPs;
* everything that belongs to the *club* stays — its books, its meetings, its
  recurring schedule — losing a reference rather than a row;
* a book suggestion stays on the shortlist, unattributed, because
  `Book.suggested_by` is nullable on purpose;
* a club is never left without an admin.

`ORPHANABLE` below is every table that references `members.id` and should be
empty afterwards. Asserting against the list rather than a handful of named
tables is deliberate: a table added later without a cascade fails these tests
instead of quietly accumulating orphans.
"""
from datetime import datetime

from app.models import (
    Book, BookReader, BookVote, Club, DiscussionPost, DiscussionPostLike,
    Discussion, Meeting, MeetingRSVP, MeetingSchedule, Member,
    MemberBookCompletion, MemberBookProgress, Rating, User, Vote,
)

ORPHANABLE = [
    MemberBookCompletion, MemberBookProgress, Rating, BookVote, BookReader,
    DiscussionPostLike, DiscussionPost, Vote, MeetingRSVP,
]


def give_the_member_a_row_in_every_table(db, club, member, book):
    """Populate one row in each table that references members.id."""
    discussion = Discussion(book_id=book.id, title="Chapter one")
    db.add(discussion)
    db.commit()

    post = DiscussionPost(discussion_id=discussion.id, author_id=member.id,
                          content="Loved it")
    db.add(post)
    db.commit()

    meeting = Meeting(club_id=club.id, host_id=member.id, title="Book night",
                      meeting_datetime=datetime(2026, 10, 1, 19, 0))
    db.add(meeting)
    db.add(MeetingSchedule(club_id=club.id, current_host_id=member.id,
                           recurrence_pattern="monthly", recurrence_details="first"))
    db.commit()

    db.add_all([
        MemberBookCompletion(member_id=member.id, book_id=book.id),
        MemberBookProgress(member_id=member.id, book_id=book.id, page=42),
        Rating(book_id=book.id, member_id=member.id, rating=5, review="Superb"),
        BookVote(book_id=book.id, member_id=member.id, vote_type="upvote"),
        BookReader(book_id=book.id, member_id=member.id),
        DiscussionPostLike(post_id=post.id, member_id=member.id),
        Vote(member_id=member.id, book_id=book.id, vote_type="upvote"),
        MeetingRSVP(meeting_id=meeting.id, member_id=member.id, status="yes"),
    ])
    db.commit()
    return meeting


def test_deleting_an_account_removes_it(world, db):
    response = world.member_client.post(
        "/profile/settings/delete", data={"confirm_username": "member"}
    )
    assert response.status_code == 303
    assert db.query(User).filter(User.username == "member").count() == 0


def test_deleting_an_account_removes_its_memberships(world, db):
    world.member_client.post("/profile/settings/delete",
                             data={"confirm_username": "member"})
    db.expire_all()
    assert db.query(Member).filter(Member.display_name == "Member").count() == 0


def test_deleting_an_account_logs_it_out(world, db):
    world.member_client.post("/profile/settings/delete",
                             data={"confirm_username": "member"})
    assert world.member_client.get("/profile/settings").headers["location"] == "/auth/login"


def test_deleting_an_account_with_activity_everywhere_still_works(world, db):
    """The demanding case: a member who has touched every table that points at
    them. Cascades have to reach all of it, or the delete fails outright."""
    give_the_member_a_row_in_every_table(db, world.club, world.member, world.book_a)

    response = world.member_client.post(
        "/profile/settings/delete", data={"confirm_username": "member"}
    )
    assert response.status_code == 303
    assert db.query(User).filter(User.username == "member").count() == 0


def test_deleting_an_account_takes_its_contributions_with_it(world, db):
    give_the_member_a_row_in_every_table(db, world.club, world.member, world.book_a)
    world.member_client.post("/profile/settings/delete",
                             data={"confirm_username": "member"})
    db.expire_all()

    for model in ORPHANABLE:
        assert db.query(model).count() == 0, f"{model.__name__} left orphaned rows"


def test_deleting_an_account_keeps_the_club_and_its_books(world, db):
    give_the_member_a_row_in_every_table(db, world.club, world.member, world.book_a)
    world.member_client.post("/profile/settings/delete",
                             data={"confirm_username": "member"})
    db.expire_all()

    assert db.query(Club).count() == 1
    assert db.query(Book).count() == 2


def test_book_suggestions_survive_their_suggester(world, db):
    """Book.suggested_by is nullable on purpose: a departing member's
    suggestions stay on the shortlist, just unattributed."""
    world.book_a.suggested_by = world.member.id
    db.commit()

    world.member_client.post("/profile/settings/delete",
                             data={"confirm_username": "member"})
    db.expire_all()

    book = db.query(Book).filter(Book.id == world.book_a.id).first()
    assert book is not None
    assert book.suggested_by is None


def test_meetings_survive_their_host(world, db):
    """A meeting belongs to the club, not the host. Losing a member must not
    delete meetings the club may still be planning around."""
    give_the_member_a_row_in_every_table(db, world.club, world.member, world.book_a)
    world.member_client.post("/profile/settings/delete",
                             data={"confirm_username": "member"})
    db.expire_all()

    meeting = db.query(Meeting).first()
    assert meeting is not None
    assert meeting.host_id is None

    schedule = db.query(MeetingSchedule).first()
    assert schedule is not None
    assert schedule.current_host_id is None


def test_an_admin_can_take_over_a_hostless_schedule(world, db):
    """Somebody has to be able to run a schedule whose host has left. Without
    this the seat could never be refilled: with `current_host_id` null, nobody
    satisfies `current_host_id == member.id`."""
    db.add(MeetingSchedule(club_id=world.club.id, current_host_id=None,
                           recurrence_pattern="monthly", recurrence_details="first"))
    db.commit()

    assert world.admin_client.get(
        f"/meetings/setup/{world.club.code}").status_code == 200
    assert world.member_client.get(
        f"/meetings/setup/{world.club.code}").status_code == 403


def test_deletion_requires_the_username_to_match(world, db):
    response = world.member_client.post(
        "/profile/settings/delete", data={"confirm_username": "not-my-name"}
    )
    assert response.status_code == 303
    assert db.query(User).filter(User.username == "member").count() == 1


def test_the_last_admin_cannot_walk_out(world, db):
    """A club with no admin can never be configured again, and nobody can
    promote a replacement."""
    response = world.admin_client.post(f"/clubs/{world.club.code}/leave")
    assert response.headers["location"] == f"/clubs/{world.club.code}/admin"
    db.expire_all()
    assert db.query(Member).filter(Member.id == world.admin.id).count() == 1


def test_a_plain_member_can_leave(world, db):
    member_id = world.member.id  # captured before the row goes away
    response = world.member_client.post(f"/clubs/{world.club.code}/leave")
    assert response.headers["location"] == "/"
    db.expire_all()
    assert db.query(Member).filter(Member.id == member_id).count() == 0


def test_leaving_a_club_leaves_no_orphans(world, db):
    give_the_member_a_row_in_every_table(db, world.club, world.member, world.book_a)
    world.member_client.post(f"/clubs/{world.club.code}/leave")
    db.expire_all()

    for model in ORPHANABLE:
        assert db.query(model).count() == 0, f"{model.__name__} left orphaned rows"


def test_an_admin_can_leave_once_someone_else_is_promoted(world, db):
    admin_id = world.admin.id
    world.admin_client.post(f"/clubs/{world.club.code}/admin/promote",
                            data={"member_id": world.member.id})
    response = world.admin_client.post(f"/clubs/{world.club.code}/leave")
    assert response.headers["location"] == "/"
    db.expire_all()
    assert db.query(Member).filter(Member.id == admin_id).count() == 0
