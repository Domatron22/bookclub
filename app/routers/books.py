from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import random

from ..database import get_db
from ..models import Book, Club, Member, BookVote

router = APIRouter()


def get_current_member(request: Request, db: Session) -> Member:
    """Get current authenticated member"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    member = db.query(Member).filter(Member.session_id == session_id).first()
    if not member:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return member


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
    # Get club
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Get current member
    member = get_current_member(request, db)
    if member.club_id != club.id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Create book suggestion
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
    
    return RedirectResponse(
        url=f"/clubs/{club.code}",
        status_code=303
    )


@router.post("/select-random/{club_code}")
async def select_random_book(
    request: Request,
    club_code: str,
    db: Session = Depends(get_db)
):
    """Randomly select a book from suggestions"""
    # Get club
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Verify member
    member = get_current_member(request, db)
    if member.club_id != club.id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Get suggested books that aren't vetoed
    suggested_books = db.query(Book).filter(
        Book.club_id == club.id,
        Book.status == "suggested",
        Book.vetoed == False
    ).all()
    
    if not suggested_books:
        raise HTTPException(status_code=400, detail="No books available to select")
    
    # Weighted random selection
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
    
    # Update selected book
    selected_book.status = "reading"
    selected_book.selected_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(
        url=f"/clubs/{club.code}",
        status_code=303
    )


@router.post("/{book_id}/complete")
async def complete_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """Mark a book as completed"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Verify member
    member = get_current_member(request, db)
    if member.club_id != book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    book.status = "completed"
    book.completed_at = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(
        url=f"/clubs/{book.club.code}",
        status_code=303
    )


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
    
    # Check if veto is enabled
    if not club.veto_enabled:
        raise HTTPException(status_code=403, detail="Veto system is disabled for this club")
    
    # Verify member
    member = get_current_member(request, db)
    if member.club_id != book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Check if member already vetoed
    existing_veto = db.query(BookVote).filter(
        BookVote.book_id == book_id,
        BookVote.member_id == member.id,
        BookVote.vote_type == "veto"
    ).first()
    
    if not existing_veto:
        # Add veto vote
        veto = BookVote(
            book_id=book_id,
            member_id=member.id,
            vote_type="veto"
        )
        db.add(veto)
        db.commit()
    
    # Calculate veto percentage
    total_members = db.query(Member).filter(Member.club_id == club.id).count()
    veto_count = db.query(BookVote).filter(
        BookVote.book_id == book_id,
        BookVote.vote_type == "veto"
    ).count()
    
    veto_percentage = (veto_count / total_members * 100) if total_members > 0 else 0
    
    # Check if veto threshold is met
    if veto_percentage >= club.veto_percentage:
        book.vetoed = True
        db.commit()
    
    return RedirectResponse(
        url=f"/clubs/{book.club.code}",
        status_code=303
    )