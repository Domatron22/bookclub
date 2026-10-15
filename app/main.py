# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

# Docker supplies these through `env_file`, but running uvicorn directly gets
# nothing — which used to mean silent fallbacks and now means a missing
# SECRET_KEY. `override=False` keeps real environment variables authoritative,
# so the container's env_file still wins.
load_dotenv("coverbound.env", override=False)

from datetime import datetime

from .database import engine, get_db, Base
from .models import Club, Member, MemberBookCompletion
from .routers import clubs, books, discussions, meetings, ratings, auth, profile, feedback
from .version import __version__
from .dependencies import get_current_user
from .templating import templates, base_context
from . import popular_books, recaps

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Coverbound",
    description="Self-hosted book club management",
    version=__version__
)

DEBUG = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes")

# The session cookie now carries the logged-in user's identity, not just flash
# messages — so an unset SECRET_KEY would mean every deployment signs sessions
# with the same public string, and anyone could forge one. Refuse to boot.
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError(
            "SECRET_KEY is unset. Session cookies carry login identity and must "
            "be signed with a secret unique to this deployment. Run `make init` "
            "or set SECRET_KEY in coverbound.env."
        )
    SECRET_KEY = "insecure-development-key"

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    # Matches the year-long login the old identity cookie granted.
    max_age=365 * 24 * 60 * 60,
    # `lax` still sends the cookie on the top-level GET that Google redirects
    # back to, which `strict` would drop — losing the OAuth state mid-flow.
    same_site="lax",
    https_only=not DEBUG,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(clubs.router, prefix="/clubs", tags=["clubs"])
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(discussions.router, prefix="/discussions", tags=["discussions"])
app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(ratings.router, prefix="/ratings", tags=["ratings"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(feedback.router, tags=["feedback"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Your clubs when signed in; the public landing page when not."""
    user = get_current_user(request, db)

    if not user:
        # Only clubs whose admin opted into the public directory.
        public_clubs = db.query(Club).filter(Club.is_public == True).all()  # noqa: E712
        return templates.TemplateResponse(
            request,
            "landing.html",
            {
                **base_context(request, db, None, screen="landing"),
                "title": "Coverbound — a cozy little book club",
                "public_clubs": public_clubs,
                "hero_books": popular_books.hero_picks(3),
            }
        )

    members = db.query(Member).filter(Member.user_id == user.id).all()
    user_clubs = [m.club for m in members]

    # Just the headline count, not the whole recap: building one aggregates
    # every completion, rating and post across all of this user's clubs, and
    # the home page only needs to know whether there is a year worth showing.
    # Only in December — the rest of the year it lives on the profile.
    year = recaps.latest_recap_year()
    member_ids = [m.id for m in members]
    recap_books = (
        db.query(MemberBookCompletion.book_id)
        .filter(
            MemberBookCompletion.member_id.in_(member_ids),
            MemberBookCompletion.completed_at >= datetime(year, 1, 1),
            MemberBookCompletion.completed_at < datetime(year + 1, 1, 1),
        )
        .distinct()
        .count()
        if member_ids and recaps.recap_season() else 0
    )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            **base_context(request, db, user),
            "title": "Coverbound - Home",
            "user_clubs": user_clubs,
            # The recap entry point only earns its place once there's a year to show.
            "personal_recap": (
                {"year": year, "books": recap_books} if recap_books else None
            ),
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": __version__}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
