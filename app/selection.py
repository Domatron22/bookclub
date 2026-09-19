# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""The handshake between drawing the club's next book and committing to it.

Both selection paths are two-step: the reel needs a target to decelerate onto,
and a closed vote needs its winner shown, before either is acknowledged. That
leaves a gap where the browser knows which book was picked but the server
doesn't — and `?picked=` in the URL is just a number the caller can edit, so a
vote would decide nothing.

So the pick is remembered server-side, in the admin's signed session, and
`/books/{id}/assign` will only commit the book that was actually drawn.
"""
from fastapi import Request

SESSION_KEY = "pending_pick"


def remember(request: Request, club_id: int, book_id: int) -> None:
    """Record which book this club just drew, pending acknowledgment."""
    request.session[SESSION_KEY] = {"club_id": club_id, "book_id": book_id}


def take(request: Request, club_id: int, book_id: int) -> bool:
    """Consume the pending pick, if it is the one being claimed.

    Single-use: acknowledging twice (a double submit, a refreshed POST) finds
    nothing the second time, so one draw can only ever assign one book.
    """
    pending = request.session.get(SESSION_KEY)
    if not isinstance(pending, dict):
        return False
    if pending.get("club_id") != club_id or pending.get("book_id") != book_id:
        return False
    request.session.pop(SESSION_KEY, None)
    return True


def clear(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)
