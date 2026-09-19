# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""A club's contents are visible only to its members.

Book ids are sequential, so an ungated book route lets anyone walk every shelf
on the instance. These tests pin that shut.
"""
import pytest


def test_anonymous_visitors_cannot_read_club_content(world):
    for path in [
        f"/books/{world.book_a.id}",
        f"/discussions/book/{world.book_a.id}",
        f"/ratings/book/{world.book_a.id}",
        f"/meetings/club/{world.club.code}",
    ]:
        assert world.anon.get(path).status_code == 401, path


def test_non_members_cannot_read_club_content(world):
    for path in [
        f"/books/{world.book_a.id}",
        f"/discussions/book/{world.book_a.id}",
        f"/ratings/book/{world.book_a.id}",
        f"/meetings/club/{world.club.code}",
    ]:
        assert world.outsider_client.get(path).status_code == 403, path


def test_members_can_read_club_content(world):
    for path in [
        f"/books/{world.book_a.id}",
        f"/discussions/book/{world.book_a.id}",
        f"/ratings/book/{world.book_a.id}",
        f"/meetings/club/{world.club.code}",
        f"/clubs/{world.club.code}",
        f"/clubs/{world.club.code}/shelf",
    ]:
        assert world.member_client.get(path).status_code == 200, path


def test_a_non_member_is_sent_to_the_join_form(world):
    """They followed a real club link. A 403 is a dead end; the join form with
    the code prefilled is the thing they actually need."""
    response = world.outsider_client.get(f"/clubs/{world.club.code}")
    assert response.status_code == 303
    assert response.headers["location"] == f"/clubs/join?code={world.club.code}"

    shelf = world.outsider_client.get(f"/clubs/{world.club.code}/shelf")
    assert shelf.status_code == 303


def test_join_form_prefills_the_code(world):
    response = world.outsider_client.get(f"/clubs/join?code={world.club.code}")
    assert response.status_code == 200
    assert f'value="{world.club.code}"' in response.text


@pytest.mark.parametrize("is_public", [True, False])
def test_public_listing_never_grants_read_access(world, db, is_public):
    """`is_public` controls listing in the directory, not readability."""
    world.club.is_public = is_public
    db.commit()

    assert world.outsider_client.get(f"/clubs/{world.club.code}").status_code == 303
    assert world.outsider_client.get(f"/books/{world.book_a.id}").status_code == 403


def test_the_directory_itself_stays_open(world, db):
    """Browsing is the one public surface — that is the point of the directory."""
    world.club.is_public = True
    db.commit()

    response = world.anon.get("/clubs/browse")
    assert response.status_code == 200
    assert world.club.name in response.text
    # ...but it must not leak a join code to someone who has not been given one.
    assert world.club.code not in response.text


def test_private_clubs_stay_out_of_the_directory(world, db):
    world.club.is_public = False
    db.commit()
    assert world.club.name not in world.anon.get("/clubs/browse").text


def test_recap_requires_membership(world):
    assert world.outsider_client.get(f"/clubs/{world.club.code}/recap").status_code == 403
    assert world.member_client.get(f"/clubs/{world.club.code}/recap").status_code == 200


def test_profiles_require_login(world):
    assert world.anon.get("/profile/admin").status_code == 303
    assert world.member_client.get("/profile/admin").status_code == 200
