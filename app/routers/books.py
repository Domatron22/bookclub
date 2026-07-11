from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import random

from ..database import get_db
from ..dependencies import require_current_user, require_member_for_club
from ..models import Book, Club, Member, BookVote, BookReader, MemberBookCompletion

router = APIRouter()


@router.post("/suggest")
async def suggest_book(
    request: Request,
    club_code: str = Form(...),
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(""),
    isbn: str = Form(""),
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
        suggested_by=member.id,
        status="suggested"
    )
    db.add(book)
    db.commit()

    return RedirectResponse(url=f"/clubs/{club.code}", status_code=303)


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
    require_member_for_club(user, club.id, db)

    suggested_books = db.query(Book).filter(
        Book.club_id == club.id,
        Book.status == "suggested",
        Book.vetoed == False
    ).all()

    if not suggested_books:
        raise HTTPException(status_code=400, detail="No books available to select")

    weights = [book.weight for book in suggested_books]
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
