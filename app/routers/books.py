# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import random

from ..database import SessionLocal, get_db
from ..dependencies import (
    require_club_admin,
    require_current_user,
    require_member_for_club,
)
from ..google_oauth import safe_next
from .. import selection
from ..templating import templates, base_context, assign_cover_colors
from .. import open_library
from ..models import (
    Book, Club, Member, BookVote, BookReader, MemberBookCompletion, MemberBookProgress
)

router = APIRouter()


# `def`, not `async def`: `open_library.search` is a blocking `requests` call
# with a 6s timeout, and a coroutine would hold the event loop for all of it —
# stalling every other request in the process. Starlette runs a sync handler in
# its threadpool.
@router.get("/search", response_class=HTMLResponse)
def search_books(
    request: Request,
    club_code: str,
    q: str = "",
    db: Session = Depends(get_db),
):
    """Search Open Library for a book to add to the club's shortlist.

    Declared before `/{book_id}` so the literal path wins the match.
    """
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    require_member_for_club(user, club.id, db)

    results, search_failed = [], False
    query = q.strip()[:200]
    if query:
        results, search_failed = open_library.search(query)

    return templates.TemplateResponse(
        request,
        "books/search.html",
        {
            **base_context(request, db, user, club=club, screen="search"),
            "title": "Add a book",
            "club": club,
            "query": q,
            "results": results,
            "search_failed": search_failed,
        },
    )


def _book_stats(book) -> dict:
    """Rating average and counts used by the shelf and book pages."""
    scores = [r.rating for r in book.ratings]
    return {
        "avg": round(sum(scores) / len(scores), 1) if scores else None,
        "reviews": len(scores),
        "discussions": len(book.discussions),
    }


@router.get("/{book_id}", response_class=HTMLResponse)
async def view_book(request: Request, book_id: int, db: Session = Depends(get_db)):
    """Look back at a book the club has finished."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    club = book.club
    # A club's reading is private to its members. Book ids are sequential, so
    # without this any visitor could walk every shelf on the instance.
    user = require_current_user(request, db)
    current_member = require_member_for_club(user, club.id, db)

    return templates.TemplateResponse(
        request,
        "books/view.html",
        {
            **base_context(request, db, user, club=club, screen="book"),
            "title": book.title,
            "book": book,
            "club": club,
            "current_member": current_member,
            "stats": _book_stats(book),
        },
    )


def attach_cover(book_id: int, title: str, author: str) -> None:
    """Fetch cover art for a new book, after the response has gone out.

    Runs on its own session — the request's is closed by the time this fires.
    A book that finds no art keeps its placeholder; `scripts/backfill_covers.py`
    sweeps up later.
    """
    found = open_library.lookup_cover(title, author, timeout=15)
    if not found:
        return

    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        # Re-check: a cover may have been set by hand in the meantime.
        if book and not book.cover_url:
            book.cover_url = found["cover_url"]
            if not book.open_library_id:
                book.open_library_id = found["open_library_id"]
            db.commit()
    finally:
        db.close()


@router.post("/suggest")
async def suggest_book(
    request: Request,
    background: BackgroundTasks,
    club_code: str = Form(...),
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(""),
    isbn: str = Form(""),
    page_count: int = Form(None),
    cover_url: str = Form(""),
    open_library_id: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db)
):
    """Add a book suggestion to the club"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, club.id, db)

    book = Book(
        club_id=club.id,
        title=title,
        author=author,
        description=description,
        isbn=isbn,
        page_count=page_count,
        cover_url=cover_url or None,
        open_library_id=open_library_id or None,
        suggested_by=member.id,
        status="suggested"
    )
    assign_cover_colors(book)
    db.add(book)
    db.commit()

    # Search results arrive with a cover; hand-typed books need one looked up.
    # After the response, so the form never hangs on Open Library.
    if not book.cover_url:
        background.add_task(attach_cover, book.id, book.title, book.author)

    request.session['flash_message'] = f'"{book.title}" is on the shortlist.'
    request.session['flash_type'] = "success"

    # Only ever redirect within this app, never to a caller-supplied host.
    # `startswith("/")` alone is not enough: `//evil.example` is protocol-
    # relative and browsers treat it as absolute.
    target = safe_next(redirect_to, f"/clubs/{club.code}")
    return RedirectResponse(url=target, status_code=303)


@router.post("/select-random/{club_code}")
async def select_random_book(
    request: Request,
    club_code: str,
    db: Session = Depends(get_db)
):
    """Randomly select a book from suggestions"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    require_club_admin(user, club.id, db)

    suggested_books = db.query(Book).filter(
        Book.club_id == club.id,
        Book.status == "suggested",
        Book.vetoed == False
    ).all()

    if not suggested_books:
        raise HTTPException(status_code=400, detail="No books available to select")

    # `weight` has a Python-side default, so rows written by a migration, the
    # seed script or raw SQL can be NULL — which `random.choices` rejects.
    weights = [book.weight or 1.0 for book in suggested_books]
    selected_book = random.choices(suggested_books, weights=weights, k=1)[0]

    # Mark current reading book as completed if exists
    current_book = db.query(Book).filter(
        Book.club_id == club.id,
        Book.status == "reading"
    ).first()
    if current_book:
        current_book.status = "completed"
        current_book.completed_at = datetime.utcnow()

    selected_book.status = "reading"
    selected_book.selected_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/clubs/{club.code}", status_code=303)


@router.post("/{book_id}/vote")
async def vote_book(request: Request, book_id: int, db: Session = Depends(get_db)):
    """Toggle this member's vote for a shortlisted book (one vote each)."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    existing = db.query(BookVote).filter(
        BookVote.book_id == book_id,
        BookVote.member_id == member.id,
        BookVote.vote_type == "upvote"
    ).first()

    if existing:
        db.delete(existing)
    else:
        # One vote per member per round — clear any vote on a sibling title.
        club_book_ids = [b.id for b in book.club.books if b.status == "suggested"]
        db.query(BookVote).filter(
            BookVote.member_id == member.id,
            BookVote.vote_type == "upvote",
            BookVote.book_id.in_(club_book_ids)
        ).delete(synchronize_session=False)
        db.add(BookVote(book_id=book_id, member_id=member.id, vote_type="upvote"))

    db.commit()
    return RedirectResponse(url=f"/clubs/{book.club.code}/select", status_code=303)


@router.post("/spin/{club_code}")
async def spin_for_book(request: Request, club_code: str, db: Session = Depends(get_db)):
    """Draw a random candidate WITHOUT assigning it.

    The reel needs a target to decelerate onto before the acknowledgment modal
    appears; the book is only assigned once that modal is acknowledged.
    """
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    require_club_admin(user, club.id, db)

    if any(b.status == "reading" for b in club.books):
        raise HTTPException(status_code=409, detail="This club already has a book on the go")

    candidates = [b for b in club.books if b.status == "suggested" and not b.vetoed]
    if not candidates:
        raise HTTPException(status_code=400, detail="No books available to select")

    pick = random.choices(candidates, weights=[b.weight or 1.0 for b in candidates], k=1)[0]
    selection.remember(request, club.id, pick.id)
    return JSONResponse({"book_id": pick.id, "title": pick.title, "author": pick.author})


@router.post("/{book_id}/assign")
async def assign_book(request: Request, book_id: int, db: Session = Depends(get_db)):
    """Lock in the club's next read (the acknowledgment step)."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = require_current_user(request, db)
    require_club_admin(user, book.club_id, db)

    # Only the book this club actually drew, and only once. Without this the
    # acknowledgment step would take any id the caller typed, and closing a
    # vote would decide nothing.
    if not selection.take(request, book.club_id, book.id):
        request.session['flash_message'] = (
            "That pick has expired — draw again so everyone sees the same result."
        )
        request.session['flash_type'] = "error"
        return RedirectResponse(url=f"/clubs/{book.club.code}/select", status_code=303)

    if book.status != "suggested":
        return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)

    current = db.query(Book).filter(
        Book.club_id == book.club_id, Book.status == "reading"
    ).first()
    if current:
        current.status = "completed"
        current.completed_at = datetime.utcnow()

    book.status = "reading"
    book.selected_at = datetime.utcnow()
    db.commit()

    request.session['flash_message'] = f'"{book.title}" is the club\'s next read.'
    request.session['flash_type'] = "success"
    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/complete")
async def archive_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Archive a book as completed (admin only)"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    if not member.is_admin:
        request.session['flash_message'] = "Only admins can archive books."
        request.session['flash_type'] = "error"
        return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)

    book.status = "completed"
    book.completed_at = datetime.utcnow()
    db.commit()

    request.session['flash_message'] = f'"{book.title}" has been archived.'
    request.session['flash_type'] = "success"

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/veto")
async def veto_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Veto a book suggestion"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    club = book.club

    if not club.veto_enabled:
        raise HTTPException(status_code=403, detail="Veto system is disabled for this club")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    existing_veto = db.query(BookVote).filter(
        BookVote.book_id == book_id,
        BookVote.member_id == member.id,
        BookVote.vote_type == "veto"
    ).first()

    if not existing_veto:
        veto = BookVote(
            book_id=book_id,
            member_id=member.id,
            vote_type="veto"
        )
        db.add(veto)
        db.commit()

    total_members = db.query(Member).filter(Member.club_id == club.id).count()
    veto_count = db.query(BookVote).filter(
        BookVote.book_id == book_id,
        BookVote.vote_type == "veto"
    ).count()

    veto_percentage = (veto_count / total_members * 100) if total_members > 0 else 0

    if veto_percentage >= club.veto_percentage:
        book.vetoed = True
        db.commit()

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/join-reading")
async def join_reading(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Join the reading group for a book"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.status != "reading":
        raise HTTPException(status_code=400, detail="This book is not currently being read")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    existing = db.query(BookReader).filter(
        BookReader.book_id == book_id,
        BookReader.member_id == member.id
    ).first()

    if not existing:
        reader = BookReader(book_id=book_id, member_id=member.id)
        db.add(reader)
        db.commit()

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/leave-reading")
async def leave_reading(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Leave the reading group for a book"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    reader = db.query(BookReader).filter(
        BookReader.book_id == book_id,
        BookReader.member_id == member.id
    ).first()

    if reader:
        db.delete(reader)
        db.commit()

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/progress")
async def update_progress(
    request: Request,
    book_id: int,
    page: int = Form(...),
    db: Session = Depends(get_db)
):
    """Set the current member's page position in a book."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not book.club.feature_progress:
        raise HTTPException(status_code=403, detail="Reading progress is turned off for this club")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    page = max(0, min(page, book.page_count or page))

    entry = db.query(MemberBookProgress).filter(
        MemberBookProgress.member_id == member.id,
        MemberBookProgress.book_id == book_id
    ).first()

    if entry:
        entry.page = page
        entry.updated_at = datetime.utcnow()
    else:
        db.add(MemberBookProgress(member_id=member.id, book_id=book_id, page=page))
    db.commit()

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/member-complete")
async def member_complete_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Toggle personal book completion on (idempotent)."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    existing = db.query(MemberBookCompletion).filter(
        MemberBookCompletion.member_id == member.id,
        MemberBookCompletion.book_id == book_id
    ).first()

    if not existing:
        completion = MemberBookCompletion(
            member_id=member.id,
            book_id=book_id,
            completed_at=datetime.utcnow()
        )
        db.add(completion)
        db.commit()

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)


@router.post("/{book_id}/member-uncomplete")
async def member_uncomplete_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Remove personal book completion (idempotent)."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    completion = db.query(MemberBookCompletion).filter(
        MemberBookCompletion.member_id == member.id,
        MemberBookCompletion.book_id == book_id
    ).first()

    if completion:
        db.delete(completion)
        db.commit()

    return RedirectResponse(url=f"/clubs/{book.club.code}", status_code=303)
