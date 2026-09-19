# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .models import Member, User

# Legacy cookie from before identity moved into the signed session. It is
# never *read* any more — it held a bare user id, so anyone could type
# `coverbound_user_id=1` into devtools and become that user. We only still
# name it so logout can clear it from browsers that carry one.
LEGACY_COOKIE_NAME = "coverbound_user_id"

# Key under which the signed session cookie carries the logged-in user's id.
SESSION_USER_KEY = "uid"

# `last_seen_at` is only ever rendered as a coarse "active recently", so there
# is nothing to gain from writing it on every request — and plenty to lose:
# every page view would be an UPDATE plus a COMMIT, and SQLite serialises
# writers across the whole process.
LAST_SEEN_RESOLUTION = timedelta(minutes=5)


def login_user(request: Request, user: User) -> None:
    """Mark the session as authenticated for `user`.

    Clears any pre-existing session state first: nothing from the logged-out
    session (OAuth state, half-finished signup) should survive into an
    authenticated one.
    """
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id


def logout_user(request: Request) -> None:
    """Drop the authenticated identity and everything else in the session."""
    request.session.clear()


def get_current_user(request: Request, db: Session) -> "User | None":
    """Return the User named by the signed session, or None if not authenticated."""
    uid = request.session.get(SESSION_USER_KEY)
    if not isinstance(uid, int):
        return None
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        # The account was deleted while the cookie was still live.
        request.session.pop(SESSION_USER_KEY, None)
        return None

    now = datetime.utcnow()
    if not user.last_seen_at or now - user.last_seen_at >= LAST_SEEN_RESOLUTION:
        user.last_seen_at = now
        db.commit()
    return user


def require_current_user(request: Request, db: Session) -> User:
    """Like get_current_user but raises 401 if not authenticated."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_member_for_club(user: "User | None", club_id: int, db: Session) -> "Member | None":
    """Return the Member record for (user_id, club_id), or None."""
    if not user:
        return None
    return db.query(Member).filter(
        Member.user_id == user.id,
        Member.club_id == club_id
    ).first()


def require_member_for_club(user: "User | None", club_id: int, db: Session) -> Member:
    """Like get_member_for_club but raises 403 if not a member."""
    member = get_member_for_club(user, club_id, db)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    return member


def require_club_admin(user: "User | None", club_id: int, db: Session) -> Member:
    """The caller's Member row, which must carry admin rights on this club.

    Anything that changes the club for everyone else — its settings, who runs
    it, and which book it is reading — goes through here, so the rule lives in
    one place rather than being re-spelled at each call site.
    """
    member = require_member_for_club(user, club_id, db)
    if not member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return member
