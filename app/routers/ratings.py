from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..dependencies import get_current_user, require_current_user, get_member_for_club, require_member_for_club
from ..models import Rating, ReviewLike, ReviewComment, ReviewCommentLike, Book

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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

    user = get_current_user(request, db)
    current_member = get_member_for_club(user, book.club_id, db)

    avg_rating = db.query(func.avg(Rating.rating)).filter(
        Rating.book_id == book_id
    ).scalar()

    user_rating = None
    if current_member:
        user_rating = db.query(Rating).filter(
            Rating.book_id == book_id,
            Rating.member_id == current_member.id
        ).first()

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
            "current_user": user,
            "current_member": current_member,
            "ratings": ratings,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "total_ratings": len(ratings),
            "user_rating": user_rating,
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

    user = require_current_user(request, db)
    member = require_member_for_club(user, book.club_id, db)

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    existing_rating = db.query(Rating).filter(
        Rating.book_id == book_id,
        Rating.member_id == member.id
    ).first()

    if existing_rating:
        existing_rating.rating = rating
        existing_rating.review = review
    else:
        new_rating = Rating(book_id=book_id, member_id=member.id, rating=rating, review=review)
        db.add(new_rating)

    db.commit()

    return RedirectResponse(url=f"/ratings/book/{book_id}", status_code=303)


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

    user = require_current_user(request, db)
    member = require_member_for_club(user, rating.book.club_id, db)

    existing_like = db.query(ReviewLike).filter(
        ReviewLike.rating_id == rating_id,
        ReviewLike.member_id == member.id
    ).first()

    if existing_like:
        db.delete(existing_like)
    else:
        like = ReviewLike(rating_id=rating_id, member_id=member.id)
        db.add(like)

    db.commit()

    return RedirectResponse(url=f"/ratings/book/{rating.book_id}", status_code=303)


@router.post("/{rating_id}/comment")
async def add_comment(
    request: Request,
    rating_id: int,
    content: str = Form(...),
    parent_comment_id: int = Form(None),
    db: Session = Depends(get_db)
):
    """Add a comment to a rating (or reply to another comment)"""
    rating = db.query(Rating).filter(Rating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, rating.book.club_id, db)

    if not content or content.strip() == "":
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    comment = ReviewComment(
        rating_id=rating_id,
        parent_comment_id=parent_comment_id,
        member_id=member.id,
        content=content.strip()
    )
    db.add(comment)
    db.commit()

    return RedirectResponse(url=f"/ratings/book/{rating.book_id}", status_code=303)


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

    user = require_current_user(request, db)
    member = require_member_for_club(user, rating.book.club_id, db)

    if rating.member_id != member.id:
        raise HTTPException(status_code=403, detail="You can only delete your own rating")

    book_id = rating.book_id
    db.delete(rating)
    db.commit()

    return RedirectResponse(url=f"/ratings/book/{book_id}", status_code=303)


@router.post("/comment/{comment_id}/like")
async def like_comment(
    request: Request,
    comment_id: int,
    db: Session = Depends(get_db)
):
    """Like or unlike a comment"""
    comment = db.query(ReviewComment).filter(ReviewComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, comment.rating.book.club_id, db)

    existing_like = db.query(ReviewCommentLike).filter(
        ReviewCommentLike.comment_id == comment_id,
        ReviewCommentLike.member_id == member.id
    ).first()

    if existing_like:
        db.delete(existing_like)
    else:
        like = ReviewCommentLike(comment_id=comment_id, member_id=member.id)
        db.add(like)

    db.commit()

    return RedirectResponse(url=f"/ratings/book/{comment.rating.book_id}", status_code=303)
