# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Registration, login, and the properties the signed session has to hold."""
from app.dependencies import LEGACY_COOKIE_NAME, SESSION_USER_KEY


def test_register_creates_account_and_reveals_secret_once(client):
    response = client.post("/auth/register", data={"username": "newreader"})
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/register/success"

    first = client.get("/auth/register/success")
    assert first.status_code == 200
    assert "newreader" in first.text

    # The secret is popped from the session, so a refresh must not re-reveal it.
    second = client.get("/auth/register/success")
    assert second.status_code == 303
    assert second.headers["location"] == "/"


def test_register_rejects_bad_usernames(client):
    for bad in ["ab", "has spaces", "hyphen-ated", "a" * 31, "emoji✨"]:
        response = client.post("/auth/register", data={"username": bad})
        assert response.status_code == 400, f"{bad!r} should have been rejected"


def test_register_rejects_duplicate_username(client, make_user):
    make_user("taken")
    response = client.post("/auth/register", data={"username": "taken"})
    assert response.status_code == 400
    assert "already taken" in response.text


def test_login_rejects_a_wrong_secret(client, make_user):
    make_user("reader")
    response = client.post(
        "/auth/login", data={"username": "reader", "account_secret": "wrong"}
    )
    assert response.status_code == 401


def test_login_rejects_an_unknown_user(client):
    response = client.post(
        "/auth/login", data={"username": "ghost", "account_secret": "whatever"}
    )
    assert response.status_code == 401


def test_google_only_account_gets_a_useful_message(client, make_user):
    """An account with no secret can only be reached through Google. Saying
    'invalid credentials' would send the owner hunting for a lost secret."""
    make_user("googler", secret=None, google_sub="sub-123")
    response = client.post(
        "/auth/login", data={"username": "googler", "account_secret": "anything"}
    )
    assert response.status_code == 401
    assert "signs in with Google" in response.text


def test_login_sets_only_the_signed_session_cookie(make_user, login):
    """Identity travels in the signed session and nowhere else. `LEGACY_COOKIE_NAME`
    is still named in the code so logout can clear it from browsers that carry
    one — but nothing should ever set it again."""
    c = login(make_user("reader"))
    assert c.cookies.get("session") is not None
    assert LEGACY_COOKIE_NAME not in c.cookies


def test_tampering_with_the_session_breaks_it(make_user, login):
    """The security property that matters: the payload is signed, so editing it
    invalidates the cookie rather than changing who you are."""
    import base64
    import json

    user = make_user("reader")
    c = login(user)
    raw = c.cookies.get("session")

    payload, _, signature = raw.partition(".")
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=="))
    assert decoded[SESSION_USER_KEY] == user.id, "sanity: the session names the user"

    forged = base64.urlsafe_b64encode(
        json.dumps({SESSION_USER_KEY: user.id + 1}).encode()
    ).decode().rstrip("=")
    c.cookies.set("session", f"{forged}.{signature}")

    assert c.get("/profile/settings").headers["location"] == "/auth/login"


def test_logout_clears_the_session(make_user, login):
    user = make_user("reader")
    c = login(user)
    assert c.get("/profile/settings").status_code == 200

    assert c.post("/auth/logout").status_code == 303
    assert c.get("/profile/settings").headers["location"] == "/auth/login"


def test_a_forged_session_is_rejected(client, make_user):
    """A cookie signed with the wrong key must not authenticate anyone."""
    make_user("reader")
    client.cookies.set("session", "eyJ1aWQiOiAxfQ==.fake.signature")
    assert client.get("/profile/settings").headers["location"] == "/auth/login"


def test_google_routes_404_when_not_configured(client):
    """No credentials configured means the buttons are hidden — the routes must
    404 rather than 500 if someone reaches them anyway."""
    assert client.get("/auth/google/login").status_code == 404
    assert client.get("/auth/google/finish").status_code == 404


def test_logged_in_users_are_bounced_off_login_and_register(make_user, login):
    c = login(make_user("reader"))
    assert c.get("/auth/login").status_code == 303
    assert c.get("/auth/register").status_code == 303
