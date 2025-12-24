from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Rating, ReviewLike, ReviewComment, Book, Member

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_current_member(request: Request, db: Session) -> Member:
    """Get current authenticated member"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    member = db.query(Member).filter(Member.session_id == session_id).first()
    if not member:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return member


@router.get("/book/{book_id}", response_class=HTMLResponse)
async def view_ratings(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """View all ratings and reviews for a book"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Get current member
    session_id = request.cookies.get("session_id")
    current_member = None
    if session_id:
        current_member = db.query(Member).filter(
            Member.session_id == session_id,
            Member.club_id == book.club_id
        ).first()
    
    # Calculate average rating
    avg_rating = db.query(func.avg(Rating.rating)).filter(
        Rating.book_id == book_id
    ).scalar()
    
    # Get user's rating if exists
    user_rating = None
    if current_member:
        user_rating = db.query(Rating).filter(
            Rating.book_id == book_id,
            Rating.member_id == current_member.id
        ).first()
    
    # Get all ratings ordered by likes
    ratings = db.query(Rating).filter(
        Rating.book_id == book_id
    ).order_by(Rating.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "ratings/list.html",
        {
            "request": request,
            "title": f"Reviews - {book.title}",
            "book": book,
            "club": book.club,
            "current_member": current_member,
            "ratings": ratings,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "total_ratings": len(ratings),
            "user_rating": user_rating
        }
    )


@router.post("/book/{book_id}/submit")
async def submit_rating(
    request: Request,
    book_id: int,
    rating: int = Form(...),
    review: str = Form(""),
    db: Session = Depends(get_db)
):
    """Submit or update a rating for a book"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    member = get_current_member(request, db)
    if member.club_id != book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Validate rating
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    # Check if user already rated
    existing_rating = db.query(Rating).filter(
        Rating.book_id == book_id,
        Rating.member_id == member.id
    ).first()
    
    if existing_rating:
        # Update existing rating
        existing_rating.rating = rating
        existing_rating.review = review
    else:
        # Create new rating
        new_rating = Rating(
            book_id=book_id,
            member_id=member.id,
            rating=rating,
            review=review
        )
        db.add(new_rating)
    
    db.commit()
    
    return RedirectResponse(
        url=f"/ratings/book/{book_id}",
        status_code=303
    )


@router.post("/{rating_id}/like")
async def like_rating(
    request: Request,
    rating_id: int,
    db: Session = Depends(get_db)
):
    """Like or unlike a rating"""
    rating = db.query(Rating).filter(Rating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    member = get_current_member(request, db)
    if member.club_id != rating.book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Check if already liked
    existing_like = db.query(ReviewLike).filter(
        ReviewLike.rating_id == rating_id,
        ReviewLike.member_id == member.id
    ).first()
    
    if existing_like:
        # Unlike
        db.delete(existing_like)
    else:
        # Like
        like = ReviewLike(
            rating_id=rating_id,
            member_id=member.id
        )
        db.add(like)
    
    db.commit()
    
    return RedirectResponse(
        url=f"/ratings/book/{rating.book_id}",
        status_code=303
    )


@router.post("/{rating_id}/comment")
async def add_comment(
    request: Request,
    rating_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    """Add a comment to a rating"""
    rating = db.query(Rating).filter(Rating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    member = get_current_member(request, db)
    if member.club_id != rating.book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Validate content
    if not content or content.strip() == "":
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    
    comment = ReviewComment(
        rating_id=rating_id,
        member_id=member.id,
        content=content.strip()
    )
    db.add(comment)
    db.commit()
    
    return RedirectResponse(
        url=f"/ratings/book/{rating.book_id}",
        status_code=303
    )


@router.post("/{rating_id}/delete")
async def delete_rating(
    request: Request,
    rating_id: int,
    db: Session = Depends(get_db)
):
    """Delete a rating (only by the author)"""
    rating = db.query(Rating).filter(Rating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    member = get_current_member(request, db)
    
    # Only the author can delete their rating
    if rating.member_id != member.id:
        raise HTTPException(status_code=403, detail="You can only delete your own rating")
    
    book_id = rating.book_id
    db.delete(rating)
    db.commit()
    
    return RedirectResponse(
        url=f"/ratings/book/{book_id}",
        status_code=303
    )