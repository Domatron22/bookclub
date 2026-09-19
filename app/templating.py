# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Shared Jinja environment and the context every page's shell needs.

Routers import `templates` from here rather than constructing their own
`Jinja2Templates`, so filters and globals are registered in one place.
"""
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .google_oauth import google_enabled
from .models import Book, Club, Member, User
from .version import __version__

templates = Jinja2Templates(directory="app/templates")

# The footer reads both of these, so a release only has to touch version.py —
# which is exactly what `update_version.sh` writes first, with package.json and
# the lockfile following it.
templates.env.globals["app_version"] = __version__

# Where this deployment's source lives. GPL gives everyone the right to the
# source of the code they are running, so a fork that changed anything should
# point this at its own repository rather than upstream.
SOURCE_URL = (os.getenv("SOURCE_URL") or "https://github.com/Domatron22/bookclub").rstrip("/")
templates.env.globals["source_url"] = SOURCE_URL

# Canonical license text, rather than a link into the repo: it says the same
# thing and cannot break on a branch rename or a private fork.
templates.env.globals["license_url"] = "https://www.gnu.org/licenses/gpl-3.0.html"


# ---------------------------------------------------------------------------
# Book covers
# ---------------------------------------------------------------------------
# A book with no cover art falls back to a flat coloured spine with its title
# set in Newsreader, from a background/foreground pair persisted on the row.
COVER_PALETTE = [
    ("#2f4a3a", "#f2ece0"),
    ("#26506b", "#e8f0f4"),
    ("#8a4a1c", "#f6e6d2"),
    ("#5a2530", "#f2e2df"),
    ("#3b3550", "#efe9df"),
    ("#b8862f", "#241a0c"),
    ("#2f2c3a", "#ece9f0"),
    ("#7a3b32", "#f4e7dd"),
    ("#274152", "#e9eff1"),
    ("#38562f", "#eef1e4"),
    ("#8a5a1f", "#f6ead2"),
    ("#4a3350", "#efe6f2"),
]


def _palette_pick(title: str, author: str) -> "tuple[str, str]":
    """The palette entry a title/author pair hashes to. Stable by construction."""
    seed = f"{title or ''}|{author or ''}"
    idx = sum(ord(c) * (i + 1) for i, c in enumerate(seed)) % len(COVER_PALETTE)
    return COVER_PALETTE[idx]


def assign_cover_colors(book) -> None:
    """Stamp a book's placeholder colours onto the row, once, at creation.

    The pick is the same one `cover_colors` would compute, so nothing changes
    visually — but writing it down is what makes the column's promise true:
    the shade survives a later edit to the title or author, which would
    otherwise re-hash the book into a different colour.
    """
    if book.cover_bg and book.cover_fg:
        return
    book.cover_bg, book.cover_fg = _palette_pick(book.title, book.author)


def cover_colors(book) -> dict:
    """Return the {bg, fg} pair for a book's placeholder cover.

    Prefers colors persisted on the row (so a cover never changes shade once
    seen), falling back to a deterministic pick keyed on title + author.
    """
    # Search results are passed in as plain dicts, not Book rows.
    get = book.get if isinstance(book, dict) else lambda k: getattr(book, k, None)

    bg, fg = get("cover_bg"), get("cover_fg")
    if bg and fg:
        return {"bg": bg, "fg": fg}

    bg, fg = _palette_pick(get("title"), get("author"))
    return {"bg": bg, "fg": fg}


# Open Library serves covers at three fixed widths: -S (~38px), -M (~180px) and
# -L (~500px). Stored URLs are the -M form.
_OL_COVER = re.compile(r"^(https://covers\.openlibrary\.org/b/(?:id|isbn|olid)/[^/?#]+)-[SML]\.jpg$")


def cover_src(url: Optional[str], size: int = 112) -> str:
    """The cover URL to request for a cover rendered `size` px wide.

    Non-Open-Library URLs pass through untouched, so a hand-entered one works.
    """
    if not url:
        return ""
    match = _OL_COVER.match(url)
    if not match:
        return url
    # Smallest variant that still holds up at 2x.
    variant = "L" if size > 90 else ("S" if size < 20 else "M")
    # default=false 404s a missing cover instead of serving a 1x1 blank, so the
    # template can fall back to the placeholder.
    return f"{match.group(1)}-{variant}.jpg?default=false"


def star_row(value, out_of: int = 5) -> list:
    """[{filled: bool}, …] for rendering a star row from a rating."""
    try:
        filled = int(round(float(value or 0)))
    except (TypeError, ValueError):
        filled = 0
    return [{"filled": n <= filled} for n in range(1, out_of + 1)]


def initial(name: Optional[str]) -> str:
    return (name or "?").strip()[:1].upper() or "?"


_NUMBER_WORDS = [
    "no", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten",
]


def numword(n) -> str:
    """Spell small counts, so prose reads 'Three clubs', not '3 clubs'."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    return _NUMBER_WORDS[n] if 0 <= n < len(_NUMBER_WORDS) else str(n)


_STATIC_DIR = Path(__file__).parent / "static"


def asset_url(path: str) -> str:
    """`/static/<path>` stamped with the file's mtime.

    Static files carry no `Cache-Control`, so browsers fall back to heuristic
    freshness and can serve a stale stylesheet for days without revalidating —
    a rebuild then ships CSS the browser never asks for. A changed file is a new
    URL; an unchanged one still caches. Stat per call so editing CSS in
    development takes effect without a restart.
    """
    url = f"/static/{path}"
    try:
        stamp = int((_STATIC_DIR / path).stat().st_mtime)
    except OSError:
        return url
    return f"{url}?v={stamp:x}"


templates.env.globals["asset_url"] = asset_url

templates.env.filters["cover_colors"] = cover_colors
templates.env.filters["cover_src"] = cover_src
templates.env.filters["star_row"] = star_row
templates.env.filters["initial"] = initial
templates.env.filters["numword"] = numword


# ---------------------------------------------------------------------------
# Friendly screen names — used by the feedback modal's "include the page I was
# on" context, so a report says "the club home", not a URL.
# ---------------------------------------------------------------------------
SCREEN_LABELS = {
    "landing": "the welcome page",
    "browse": "the club directory",
    "home": "your clubs",
    "club": "the club home",
    "create": "create a club",
    "join": "join a club",
    "admin": "club admin",
    "meetings": "the meeting schedule",
    "mcreate": "schedule a meeting",
    "mrsvp": "an RSVP",
    "msetup": "meeting settings",
    "discussions": "the discussion list",
    "thread": "a discussion",
    "ratings": "reviews & ratings",
    "profile": "a profile",
    "settings": "account settings",
    "book": "a book page",
    "shelf": "the shelf",
    "select": "choosing the next book",
    "search": "book search",
    "empty": "a new club",
    "recap": "the club's year in books",
    "urecap": "your year in books",
    "login": "log in",
    "register": "register",
    "gfinish": "choosing a username",
    "regsuccess": "account created",
}

# Ordered most-specific first; the first match wins.
_PATH_SCREENS = [
    (r"^/$", "home"),
    (r"^/clubs/browse$", "browse"),
    (r"^/clubs/create$", "create"),
    (r"^/clubs/join$", "join"),
    (r"^/clubs/[^/]+/admin", "admin"),
    (r"^/clubs/[^/]+/shelf$", "shelf"),
    (r"^/clubs/[^/]+/select$", "select"),
    (r"^/clubs/[^/]+/welcome$", "empty"),
    (r"^/clubs/[^/]+/recap$", "recap"),
    (r"^/clubs/[^/]+$", "club"),
    (r"^/meetings/club/", "meetings"),
    (r"^/meetings/create/", "mcreate"),
    (r"^/meetings/setup/", "msetup"),
    (r"^/meetings/[^/]+/rsvp$", "mrsvp"),
    (r"^/discussions/book/", "discussions"),
    (r"^/discussions/[^/]+$", "thread"),
    (r"^/ratings/book/", "ratings"),
    (r"^/books/search", "search"),
    (r"^/books/[^/]+$", "book"),
    (r"^/profile/settings", "settings"),
    (r"^/profile/recap$", "urecap"),
    (r"^/profile/", "profile"),
    (r"^/auth/google/finish", "gfinish"),
    (r"^/auth/login", "login"),
    (r"^/auth/register/success", "regsuccess"),
    (r"^/auth/register", "register"),
]

# Screens whose header strips down to the wordmark + theme toggle.
BARE_HEADER_SCREENS = {"login", "register", "regsuccess", "landing", "gfinish"}

# Every screen and flow below has shipped. The dict is kept because templates
# check it before linking to optional routes, and it is the single place to
# turn one off if a deployment doesn't want it.
FEATURES = {
    "book_page": True,      # /books/{id} and /clubs/{code}/shelf
    "select": True,         # /clubs/{code}/select — voting + random reel
    "search": True,         # /books/search — Open Library
    "recap": True,          # /clubs/{code}/recap and /profile/recap
    "feedback": True,       # POST /feedback — GitHub issue creation
    "club_features": True,  # admin "Club features" section (needs the 004 columns)
    "browse": True,         # /clubs/browse — public club directory
}
# `progress` is deliberately absent: per-member reading progress is a per-club
# setting (`Club.feature_progress`), checked server-side, not an instance-wide
# one. A key here that no template reads would just be a lie.

# Screens that count as "inside a club", so the club nav tab reads as active.
CLUB_SCREENS = {
    "club", "admin", "meetings", "mcreate", "mrsvp", "msetup", "discussions",
    "thread", "ratings", "book", "shelf", "select", "search", "empty", "recap",
}


def screen_for_path(path: str) -> str:
    for pattern, key in _PATH_SCREENS:
        if re.search(pattern, path):
            return key
    return "home"


# ---------------------------------------------------------------------------
# Shell context
# ---------------------------------------------------------------------------
def base_context(
    request: Request,
    db: Session,
    user: Optional[User],
    club: Optional[Club] = None,
    screen: Optional[str] = None,
) -> dict:
    """Everything base.html needs: the clubs switcher, nav state, screen label.

    Spread into each route's TemplateResponse context:

        {**base_context(request, db, user, club=club), "title": ..., ...}
    """
    screen = screen or screen_for_path(request.url.path)
    if screen == "home" and not user:
        screen = "landing"

    switcher_clubs = []
    if user:
        memberships = (
            db.query(Member)
            .filter(Member.user_id == user.id)
            .order_by(Member.joined_at)
            .all()
        )
        for m in memberships:
            c = m.club
            if not c:
                continue
            reading = next((b for b in c.books if b.status == "reading"), None)
            switcher_clubs.append({
                "name": c.name,
                "code": c.code,
                "members": len(c.members),
                "reading": reading.title if reading else None,
                "cover": cover_colors(reading) if reading else {"bg": "#3b3550", "fg": "#efe9df"},
                "cover_url": reading.cover_url if reading else None,
                "active": bool(club and c.id == club.id),
            })

    return {
        "request": request,
        "current_user": user,
        "features": FEATURES,
        "screen": screen,
        "screen_label": SCREEN_LABELS.get(screen, "this page"),
        "bare_header": screen in BARE_HEADER_SCREENS,
        # Templates hide every Google affordance when the deployment has no
        # OAuth credentials, so a self-hoster never sees a button that 404s.
        "google_enabled": google_enabled(),
        "in_club_section": screen in CLUB_SCREENS,
        "nav_club": club,
        "switcher_clubs": switcher_clubs,
    }
