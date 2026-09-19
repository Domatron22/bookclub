# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""In-app feedback: stores a row, then mirrors it to a GitHub issue."""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_current_user
from ..github_issues import create_issue
from ..google_oauth import safe_next
from ..models import Feedback
from ..rate_limit import check as rate_limit_check

router = APIRouter()

VALID_KINDS = {"idea", "bug", "confusing", "praise"}

# Each accepted submission can create a GitHub issue, so this endpoint spends a
# write on someone else's infrastructure. Generous enough that nobody reporting
# a genuine problem hits it, tight enough that the issue tracker can't be
# flooded from one account.
RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 60 * 60


# Defined as `def`, not `async def`, on purpose: `create_issue` is a blocking
# `requests` call, and a coroutine would hold the event loop for the length of
# it. Starlette runs a sync handler in its threadpool instead.
@router.post("/feedback")
def submit_feedback(
    request: Request,
    summary: str = Form(...),
    kind: str = Form("idea"),
    details: str = Form(""),
    include_context: bool = Form(False),
    screen_label: str = Form(""),
    user_agent: str = Form(""),
    db: Session = Depends(get_db),
):
    """Store the feedback, then try to open an issue for it.

    The row is committed before the network call, so a GitHub outage can never
    cost us the report. A failed or unconfigured call simply returns no issue
    number and the toast drops its reference.
    """
    # Sign-in required: an open endpoint that files GitHub issues is an open
    # invitation to fill the tracker with junk. It also gives every report an
    # account to follow up with.
    user = require_current_user(request, db)

    wants_json = "application/json" in request.headers.get("accept", "")

    allowed, retry_after = rate_limit_check(
        f"feedback:{user.id}", RATE_LIMIT, RATE_WINDOW_SECONDS
    )
    if not allowed:
        message = (
            f"That's {RATE_LIMIT} pieces of feedback in an hour — thank you, "
            "genuinely. Give it a little while before sending more."
        )
        if wants_json:
            return JSONResponse(
                {"ok": False, "error": message},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        request.session["flash_message"] = message
        request.session["flash_type"] = "error"
        return RedirectResponse(url=_return_target(request), status_code=303)

    summary = summary.strip()
    if not summary:
        if wants_json:
            return JSONResponse({"ok": False, "error": "Summary is required."}, status_code=400)
        request.session["flash_message"] = "Feedback needs a summary."
        request.session["flash_type"] = "error"
        return RedirectResponse(url=_return_target(request), status_code=303)

    entry = Feedback(
        user_id=user.id,
        kind=kind if kind in VALID_KINDS else "idea",
        summary=summary[:300],
        details=details.strip() or None,
        include_context=include_context,
        screen_label=(screen_label.strip()[:100] or None) if include_context else None,
        user_agent=(user_agent.strip()[:400] or None) if include_context else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    issue_number = create_issue(entry)
    if issue_number:
        entry.github_issue_number = issue_number
        db.commit()

    if wants_json:
        return JSONResponse({"ok": True, "issue_number": issue_number})

    request.session["flash_message"] = "Feedback sent — thank you."
    request.session["flash_type"] = "success"
    return RedirectResponse(url=_return_target(request), status_code=303)


def _return_target(request: Request) -> str:
    """Where to send a no-JS reporter back to.

    Only ever a path on this site: `Referer` is attacker-influencable, and a
    form on another origin posting here would otherwise bounce the user
    off-site.
    """
    referer = request.headers.get("referer", "")
    if not referer:
        return "/"

    parsed = urlparse(referer)
    if parsed.netloc and parsed.netloc == request.url.netloc:
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        return safe_next(path)
    return safe_next(referer)
