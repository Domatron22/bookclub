# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Choosing the club's next read.

Two rules hold this together: only an admin may decide, and the book that gets
assigned must be the one that was actually drawn. `?picked=` is a number in a
URL the caller controls, so the pick is held server-side and consumed once.
"""
from app.models import Book, BookVote


def reload_book(db, book_id):
    db.expire_all()
    return db.query(Book).filter(Book.id == book_id).first()


def test_members_cannot_choose_the_next_read(world):
    assert world.member_client.post(f"/books/spin/{world.club.code}").status_code == 403
    assert world.member_client.post(
        f"/books/select-random/{world.club.code}").status_code == 403
    assert world.member_client.post(
        f"/books/{world.book_a.id}/assign").status_code == 403
    assert world.member_client.post(
        f"/clubs/{world.club.code}/close-voting").status_code == 403


def test_outsiders_cannot_either(world):
    assert world.outsider_client.post(f"/books/spin/{world.club.code}").status_code == 403


def test_spin_draws_one_of_the_shortlisted_books(world):
    response = world.admin_client.post(f"/books/spin/{world.club.code}")
    assert response.status_code == 200
    body = response.json()
    assert body["book_id"] in {world.book_a.id, world.book_b.id}
    assert body["title"] in {"Dune", "Circe"}


def test_spin_does_not_assign_anything_by_itself(world, db):
    """The reel needs a target before the modal appears; the book is only
    committed once that modal is acknowledged."""
    world.admin_client.post(f"/books/spin/{world.club.code}")
    assert db.query(Book).filter(Book.status == "reading").count() == 0


def test_spin_refuses_when_the_shortlist_is_empty(world, db):
    db.query(Book).filter(Book.club_id == world.club.id).delete()
    db.commit()
    assert world.admin_client.post(f"/books/spin/{world.club.code}").status_code == 400


def test_select_random_starts_the_club_reading(world, db):
    response = world.admin_client.post(f"/books/select-random/{world.club.code}")
    assert response.status_code == 303
    assert db.query(Book).filter(Book.status == "reading").count() == 1


def test_select_random_retires_the_previous_book(world, db):
    world.book_a.status = "reading"
    db.commit()
    world.admin_client.post(f"/books/select-random/{world.club.code}")
    db.expire_all()

    assert reload_book(db, world.book_a.id).status == "completed"
    assert reload_book(db, world.book_b.id).status == "reading"


# A weight of NULL is not hypothetical: the column's default is Python-side, so
# any row written by a migration, the seed script or raw SQL has one — and
# `random.choices` raises on it rather than treating it as unweighted.
def test_drawing_works_when_a_book_has_no_weight(world, db, null_weight):
    null_weight(world.book_a)
    assert world.admin_client.post(f"/books/spin/{world.club.code}").status_code == 200


def test_select_random_works_when_a_book_has_no_weight(world, db, null_weight):
    null_weight(world.book_a)
    assert world.admin_client.post(
        f"/books/select-random/{world.club.code}").status_code == 303
    assert db.query(Book).filter(Book.status == "reading").count() == 1


def test_assign_without_a_draw_does_nothing(world, db):
    response = world.admin_client.post(f"/books/{world.book_a.id}/assign")
    assert response.status_code == 303
    assert reload_book(db, world.book_a.id).status == "suggested"


def test_assign_only_accepts_the_book_that_was_drawn(world, db):
    drawn = world.admin_client.post(f"/books/spin/{world.club.code}").json()["book_id"]
    other = world.book_b.id if drawn == world.book_a.id else world.book_a.id

    world.admin_client.post(f"/books/{other}/assign")
    assert reload_book(db, other).status == "suggested"
    assert db.query(Book).filter(Book.status == "reading").count() == 0

    world.admin_client.post(f"/books/{drawn}/assign")
    assert reload_book(db, drawn).status == "reading"


def test_a_draw_can_only_be_spent_once(world, db):
    """Guards a double submit or a refreshed POST from assigning twice."""
    drawn = world.admin_client.post(f"/books/spin/{world.club.code}").json()["book_id"]
    world.admin_client.post(f"/books/{drawn}/assign")

    world.admin_client.post(f"/books/{drawn}/assign")
    assert db.query(Book).filter(Book.status == "reading").count() == 1


def test_one_admins_draw_is_not_another_admins_to_spend(world, db, make_user,
                                                        member_factory, login):
    """The pick lives in the drawing admin's session, not in shared state."""
    second = make_user("admin2")
    member_factory(world.club, second, "Admin Two", is_admin=True)
    second_client = login(second)

    drawn = world.admin_client.post(f"/books/spin/{world.club.code}").json()["book_id"]
    second_client.post(f"/books/{drawn}/assign")
    assert db.query(Book).filter(Book.status == "reading").count() == 0


def test_spin_refuses_while_a_book_is_already_being_read(world, db):
    world.book_a.status = "reading"
    db.commit()
    assert world.admin_client.post(f"/books/spin/{world.club.code}").status_code == 409


def test_closing_a_vote_with_no_votes_decides_nothing(world, db):
    response = world.admin_client.post(f"/clubs/{world.club.code}/close-voting")
    assert response.status_code == 303
    assert db.query(Book).filter(Book.status == "reading").count() == 0


def test_closing_a_vote_respects_the_threshold(world, db):
    """Two members at 50% needs one vote; at 100% it needs two."""
    world.club.voting_percentage = 100
    db.add(BookVote(book_id=world.book_a.id, member_id=world.member.id,
                    vote_type="upvote"))
    db.commit()

    world.admin_client.post(f"/clubs/{world.club.code}/close-voting")
    assert db.query(Book).filter(Book.status == "reading").count() == 0, (
        "one vote of a required two must not carry the book"
    )

    db.add(BookVote(book_id=world.book_a.id, member_id=world.admin.id,
                    vote_type="upvote"))
    db.commit()
    response = world.admin_client.post(f"/clubs/{world.club.code}/close-voting")
    assert f"picked={world.book_a.id}" in response.headers["location"]


def test_a_tie_is_not_broken_by_list_order(world, db):
    world.club.voting_percentage = 50
    db.add_all([
        BookVote(book_id=world.book_a.id, member_id=world.admin.id, vote_type="upvote"),
        BookVote(book_id=world.book_b.id, member_id=world.member.id, vote_type="upvote"),
    ])
    db.commit()

    response = world.admin_client.post(f"/clubs/{world.club.code}/close-voting")
    assert "picked=" not in response.headers["location"]
    assert db.query(Book).filter(Book.status == "reading").count() == 0


def test_a_won_vote_is_binding(world, db):
    """Closing the vote must be what authorises the assign, end to end."""
    world.club.voting_percentage = 50
    db.add(BookVote(book_id=world.book_b.id, member_id=world.member.id,
                    vote_type="upvote"))
    db.commit()

    world.admin_client.post(f"/clubs/{world.club.code}/close-voting")
    world.admin_client.post(f"/books/{world.book_a.id}/assign")
    assert reload_book(db, world.book_a.id).status == "suggested", (
        "the losing book must not be assignable off the back of the winner's draw"
    )

    world.admin_client.post(f"/books/{world.book_b.id}/assign")
    assert reload_book(db, world.book_b.id).status == "reading"


def test_members_can_still_suggest_and_vote(world, db):
    """Admin-only selection must not turn the club into a dictatorship."""
    response = world.member_client.post("/books/suggest", data={
        "club_code": world.club.code, "title": "Piranesi", "author": "Clarke",
    })
    assert response.status_code == 303
    assert db.query(Book).filter(Book.title == "Piranesi").count() == 1

    assert world.member_client.post(f"/books/{world.book_a.id}/vote").status_code == 303
    assert db.query(BookVote).filter(
        BookVote.member_id == world.member.id, BookVote.vote_type == "upvote"
    ).count() == 1


def test_a_member_holds_only_one_vote(world, db):
    world.member_client.post(f"/books/{world.book_a.id}/vote")
    world.member_client.post(f"/books/{world.book_b.id}/vote")
    votes = db.query(BookVote).filter(
        BookVote.member_id == world.member.id, BookVote.vote_type == "upvote"
    ).all()
    assert len(votes) == 1
    assert votes[0].book_id == world.book_b.id


def test_suggest_only_redirects_within_this_site(world):
    """`redirect_to` is caller-supplied. `//evil.example` is protocol-relative,
    which browsers treat as absolute, so a bare `startswith("/")` is not enough."""
    for hostile in ["//evil.example", "https://evil.example/x", "///evil.example"]:
        response = world.member_client.post("/books/suggest", data={
            "club_code": world.club.code, "title": "T", "author": "A",
            "redirect_to": hostile,
        })
        assert response.headers["location"] == f"/clubs/{world.club.code}", hostile
