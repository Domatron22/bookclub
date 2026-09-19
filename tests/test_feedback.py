# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""In-app feedback.

Every accepted submission can spend a write on an external issue tracker, so
the endpoint needs an account behind it and a ceiling on how fast one account
can use it.
"""
from app.models import Feedback
from app.routers.feedback import RATE_LIMIT

JSON = {"Accept": "application/json"}


def test_anonymous_feedback_is_refused(world, db):
    assert world.anon.post("/feedback", data={"summary": "hi"}).status_code == 401
    assert db.query(Feedback).count() == 0


def test_a_member_can_send_feedback(world, db):
    response = world.member_client.post(
        "/feedback", data={"summary": "The shelf is lovely", "kind": "praise"},
        headers=JSON,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    entry = db.query(Feedback).one()
    assert entry.summary == "The shelf is lovely"
    assert entry.kind == "praise"
    assert entry.user_id == world.member_user.id
    # No GITHUB_TOKEN in the test environment, so no issue is filed.
    assert entry.github_issue_number is None


def test_feedback_is_rate_limited_per_account(world, db):
    codes = [
        world.member_client.post("/feedback", data={"summary": f"note {i}"},
                                 headers=JSON).status_code
        for i in range(RATE_LIMIT + 2)
    ]
    assert codes == [200] * RATE_LIMIT + [429, 429]
    assert db.query(Feedback).count() == RATE_LIMIT


def test_the_limit_is_per_account_not_global(world, db):
    for i in range(RATE_LIMIT):
        world.member_client.post("/feedback", data={"summary": f"n{i}"}, headers=JSON)

    assert world.member_client.post(
        "/feedback", data={"summary": "one more"}, headers=JSON).status_code == 429
    assert world.admin_client.post(
        "/feedback", data={"summary": "mine"}, headers=JSON).status_code == 200


def test_a_rejected_attempt_carries_retry_after(world):
    for i in range(RATE_LIMIT):
        world.member_client.post("/feedback", data={"summary": f"n{i}"}, headers=JSON)
    response = world.member_client.post("/feedback", data={"summary": "x"}, headers=JSON)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_an_empty_summary_is_refused(world, db):
    response = world.member_client.post("/feedback", data={"summary": "   "},
                                        headers=JSON)
    assert response.status_code == 400
    assert db.query(Feedback).count() == 0


def test_an_unknown_kind_falls_back_rather_than_failing(world, db):
    world.member_client.post(
        "/feedback", data={"summary": "x", "kind": "nonsense"}, headers=JSON)
    assert db.query(Feedback).one().kind == "idea"


def test_context_is_only_stored_when_it_was_offered(world, db):
    world.member_client.post("/feedback", data={
        "summary": "no context", "screen_label": "the club home",
        "user_agent": "Mozilla/5.0", "include_context": "false",
    }, headers=JSON)
    entry = db.query(Feedback).one()
    assert entry.screen_label is None
    assert entry.user_agent is None


def test_context_is_stored_when_it_was(world, db):
    world.member_client.post("/feedback", data={
        "summary": "with context", "screen_label": "the club home",
        "user_agent": "Mozilla/5.0", "include_context": "true",
    }, headers=JSON)
    entry = db.query(Feedback).one()
    assert entry.screen_label == "the club home"
    assert entry.user_agent == "Mozilla/5.0"


def test_the_no_js_fallback_only_returns_to_this_site(world):
    """Referer is attacker-influencable; a form on another origin posting here
    must not send the reporter away from the site."""
    response = world.member_client.post(
        "/feedback", data={"summary": "x"},
        headers={"Referer": "https://evil.example/trap"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_the_no_js_fallback_returns_to_a_local_page(world):
    response = world.member_client.post(
        "/feedback", data={"summary": "x"},
        headers={"Referer": f"http://testserver/clubs/{world.club.code}"},
    )
    assert response.headers["location"] == f"/clubs/{world.club.code}"
