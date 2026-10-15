# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Series titles in book search, join requests for public clubs, and when the
year-in-books recap opens."""
from datetime import datetime

import pytest
import requests

from app import recaps
from app.models import JoinRequest, Member, MemberBookCompletion
# Bound at import, before conftest's autouse stub replaces the module attribute.
from app.open_library import search as real_search


# ---------------------------------------------------------------------------
# Book search: series catalogued as "Series: Volume"
# ---------------------------------------------------------------------------

def _work(title, subtitle=None, edition_subtitle=None, cover=1, edition_cover=None):
    doc = {"key": f"/works/{title}{subtitle}", "title": title, "author_name": ["A"],
           "cover_i": cover}
    if subtitle:
        doc["subtitle"] = subtitle
    if edition_subtitle:
        doc["editions"] = {"docs": [{"subtitle": edition_subtitle, "cover_i": edition_cover}]}
    return doc


@pytest.fixture
def catalog(monkeypatch):
    """Serve `docs` as the Open Library response to the real `search`."""
    def _serve(*docs):
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"docs": list(docs)}

        monkeypatch.setattr(requests, "get", lambda *a, **k: Response())
    return _serve


def test_series_volumes_are_titled_by_their_subtitle(catalog):
    catalog(_work("Awaken Online", "Hellion"), _work("Awaken Online", "Inferno"))
    results, failed = real_search("awaken online")
    assert not failed
    assert [r["title"] for r in results] == ["Awaken Online: Hellion", "Awaken Online: Inferno"]


def test_a_work_without_a_subtitle_borrows_its_matched_editions_when_titles_clash(catalog):
    # Open Library has merged several volumes into one work; the edition that
    # matched carries the volume name and the right cover.
    catalog(
        _work("Awaken Online", edition_subtitle="Catharsis", cover=1, edition_cover=99),
        _work("Awaken Online", "Hellion"),
    )
    results, _ = real_search("awaken online")
    assert results[0]["title"] == "Awaken Online: Catharsis"
    assert results[0]["cover_url"].endswith("/99-M.jpg")


def test_the_query_naming_the_volume_is_enough_to_borrow_it(catalog):
    catalog(_work("Awaken Online", edition_subtitle="Catharsis"))
    results, _ = real_search("awaken online catharsis")
    assert results[0]["title"] == "Awaken Online: Catharsis"


def test_noisy_edition_subtitles_are_left_off_unambiguous_titles(catalog):
    catalog(_work("Dune Messiah", edition_subtitle="Dune Chronicles, Book 2", cover=5,
                  edition_cover=6))
    results, _ = real_search("dune messiah")
    assert results[0]["title"] == "Dune Messiah"
    assert results[0]["cover_url"].endswith("/5-M.jpg")


# ---------------------------------------------------------------------------
# Join requests
# ---------------------------------------------------------------------------

@pytest.fixture
def public(world, db):
    world.club.is_public = True
    db.commit()
    return world


def _request(client, club, name="Newcomer"):
    return client.post(f"/clubs/browse/{club.id}/request", data={"display_name": name})


def test_requesting_to_join_a_public_club_waits_for_an_admin(public, db):
    response = _request(public.outsider_client, public.club)
    assert response.status_code == 303

    assert db.query(JoinRequest).filter_by(user_id=public.outsider_user.id).count() == 1
    assert db.query(Member).filter_by(user_id=public.outsider_user.id).count() == 0
    assert "Request sent" in public.outsider_client.get("/clubs/browse").text


def test_private_clubs_cannot_be_requested(world, db):
    assert _request(world.outsider_client, world.club).status_code == 404
    assert db.query(JoinRequest).count() == 0


def test_asking_twice_leaves_one_request(public, db):
    _request(public.outsider_client, public.club)
    _request(public.outsider_client, public.club)
    assert db.query(JoinRequest).count() == 1


def test_an_admin_approval_makes_a_member(public, db):
    _request(public.outsider_client, public.club, "New Reader")
    join_request = db.query(JoinRequest).one()

    response = public.admin_client.post(
        f"/clubs/{public.club.code}/admin/requests/{join_request.id}/approve")
    assert response.status_code == 303

    db.expire_all()
    member = db.query(Member).filter_by(user_id=public.outsider_user.id).one()
    assert member.display_name == "New Reader"
    assert not member.is_admin
    assert db.query(JoinRequest).count() == 0
    assert public.outsider_client.get(f"/clubs/{public.club.code}").status_code == 200


def test_declining_removes_the_request_without_a_membership(public, db):
    _request(public.outsider_client, public.club)
    join_request = db.query(JoinRequest).one()

    public.admin_client.post(f"/clubs/{public.club.code}/admin/requests/{join_request.id}/decline")

    db.expire_all()
    assert db.query(JoinRequest).count() == 0
    assert db.query(Member).filter_by(user_id=public.outsider_user.id).count() == 0


def test_only_admins_can_approve(public, db):
    _request(public.outsider_client, public.club)
    join_request = db.query(JoinRequest).one()

    response = public.member_client.post(
        f"/clubs/{public.club.code}/admin/requests/{join_request.id}/approve")
    assert response.status_code == 403
    assert db.query(Member).filter_by(user_id=public.outsider_user.id).count() == 0


def test_requests_are_scoped_to_their_club(public, db, club_factory, member_factory, login,
                                           make_user):
    _request(public.outsider_client, public.club)
    join_request = db.query(JoinRequest).one()

    # An admin of some other club can't approve it through their own club's URL.
    other = club_factory(name="Elsewhere", code="OTHER001")
    rival = make_user("rival")
    member_factory(other, rival, is_admin=True)
    response = login(rival).post(f"/clubs/{other.code}/admin/requests/{join_request.id}/approve")
    assert response.status_code == 404


def test_the_requester_can_withdraw(public, db):
    _request(public.outsider_client, public.club)
    public.outsider_client.post(f"/clubs/browse/{public.club.id}/request/cancel")
    assert db.query(JoinRequest).count() == 0


def test_joining_with_the_code_clears_a_pending_request(public, db):
    _request(public.outsider_client, public.club)
    public.outsider_client.post(
        "/clubs/join", data={"code": public.club.code, "display_name": "Coded"})
    db.expire_all()
    assert db.query(JoinRequest).count() == 0
    assert db.query(Member).filter_by(user_id=public.outsider_user.id).count() == 1


def test_admins_see_pending_requests(public):
    _request(public.outsider_client, public.club, "Hopeful")
    assert "Hopeful" in public.admin_client.get(f"/clubs/{public.club.code}/admin").text


def test_the_directory_never_reveals_the_club_code(public):
    assert public.club.code not in public.outsider_client.get("/clubs/browse").text


def test_deleting_an_account_takes_its_requests(public, db):
    _request(public.outsider_client, public.club)
    public.outsider_client.post(
        "/profile/settings/delete", data={"confirm_username": public.outsider_user.username})
    db.expire_all()
    assert db.query(JoinRequest).count() == 0


# ---------------------------------------------------------------------------
# Year in books opens on December 1st
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("today, latest", [
    (datetime(2026, 1, 1), 2025),
    (datetime(2026, 11, 30, 23, 59), 2025),
    (datetime(2026, 12, 1), 2026),
    (datetime(2026, 12, 31), 2026),
])
def test_a_years_recap_opens_on_december_first(today, latest):
    assert recaps.latest_recap_year(today) == latest
    assert recaps.recap_available(latest, today)
    assert not recaps.recap_available(latest + 1, today)


@pytest.fixture
def on(monkeypatch):
    def _set(*date):
        monkeypatch.setattr(recaps, "_today", lambda: datetime(*date))
    return _set


@pytest.fixture
def finished_this_year(world, db):
    """The member finished a book in 2026, the club in 2025 and 2026."""
    world.book_a.status = "completed"
    world.book_a.completed_at = datetime(2026, 3, 1)
    world.book_b.status = "completed"
    world.book_b.completed_at = datetime(2025, 6, 1)
    db.add(MemberBookCompletion(member_id=world.member.id, book_id=world.book_a.id,
                                completed_at=datetime(2026, 3, 1)))
    db.commit()
    return world


def test_the_home_banner_waits_for_december(finished_this_year, on):
    on(2026, 10, 15)
    assert "/profile/recap" not in finished_this_year.member_client.get("/").text
    on(2026, 12, 1)
    assert "Your 2026 in books" in finished_this_year.member_client.get("/").text


def test_the_club_banner_waits_for_december(finished_this_year, on):
    url = f"/clubs/{finished_this_year.club.code}"
    on(2026, 10, 15)
    assert f"{url}/recap\"" not in finished_this_year.member_client.get(url).text
    on(2026, 12, 1)
    assert f"{url}/recap\"" in finished_this_year.member_client.get(url).text


def test_the_current_years_recap_is_closed_until_december(finished_this_year, on):
    client = finished_this_year.member_client
    on(2026, 10, 15)
    assert client.get("/profile/recap?year=2026").status_code == 404
    assert client.get(f"/clubs/{finished_this_year.club.code}/recap?year=2026").status_code == 404
    # The default is the latest open year, not the one in progress.
    assert "2025, in books." in client.get(f"/clubs/{finished_this_year.club.code}/recap").text

    on(2026, 12, 1)
    assert client.get("/profile/recap?year=2026").status_code == 200


def test_past_recaps_are_listed_on_your_own_profile(finished_this_year, on):
    w = finished_this_year
    on(2026, 10, 15)
    assert "/profile/recap?year=2026" not in w.member_client.get("/profile/member").text

    on(2027, 2, 1)
    assert "/profile/recap?year=2026" in w.member_client.get("/profile/member").text
    # Never on someone else's: the link would show the viewer their own year.
    assert "/profile/recap?year" not in w.admin_client.get("/profile/member").text


def test_the_shelf_links_to_open_club_recaps(finished_this_year, on):
    w = finished_this_year
    on(2026, 10, 15)
    shelf = w.member_client.get(f"/clubs/{w.club.code}/shelf").text
    assert "recap?year=2025" in shelf
    assert "recap?year=2026" not in shelf
