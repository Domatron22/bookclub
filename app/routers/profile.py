from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import COOKIE_NAME, get_current_user, require_current_user
from ..models import (
    User, Member, Book, MemberBookCompletion,
    Rating, BookVote, MeetingRSVP, ReviewLike, ReviewComment,
    ReviewCommentLike, DiscussionPostLike, DiscussionCommentLike,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_reading_history(profile_user, db):
    """Return reading history for visible clubs, newest first."""
    rows = (
        db.query(MemberBookCompletion, Book, Member)
        .join(Book, MemberBookCompletion.book_id == Book.id)
        .join(Member, MemberBookCompletion.member_id == Member.id)
        .filter(
            Member.user_id == profile_user.id,
            Member.profile_visible == True,
        )
        .order_by(MemberBookCompletion.completed_at.desc())
        .all()
    )
    return [
        {
            "book_title":   book.title,
            "book_author":  book.author,
            "club_name":    member.club.name,
            "club_code":    member.club.code,
            "completed_at": completion.completed_at,
        }
        for completion, book, member in rows
    ]


def _get_stats(profile_user):
    """Compute reading stats based on visible clubs."""
    visible_members = [m for m in profile_user.members if m.profile_visible]
    total_books_read = sum(len(m.book_completions) for m in visible_members)
    club_count = len(visible_members)
    most_active = max(
        visible_members,
        key=lambda m: len(m.book_completions),
        default=None,
    )
    most_active_club = (
        most_active.club.name
        if most_active and most_active.book_completions
        else None
    )
    return {
        "total_books_read": total_books_read,
        "club_count": club_count,
        "most_active_club": most_active_club,
    }


# ---------------------------------------------------------------------------
# Settings routes (must be declared BEFORE /{username} to avoid capture)
# ---------------------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Render the account settings page."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    flash_message = request.session.pop("flash_message", None)
    flash_type = request.session.pop("flash_type", "success")

    members = sorted(user.members, key=lambda m: m.club.name)

    return templates.TemplateResponse(
        "profile/settings.html",
        {
            "request": request,
            "title": "Account Settings",
            "current_user": user,
            "flash_message": flash_message,
            "flash_type": flash_type,
            "members": members,
        },
    )


@router.post("/settings/account")
async def update_account(
    request: Request,
    display_name: str = Form(""),
    db: Session = Depends(get_db),
):
    """Update the account-level display name."""
    user = require_current_user(request, db)
    user.display_name = display_name.strip() or None
    db.commit()
    request.session["flash_message"] = "Display name updated."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/profile/settings", status_code=303)


@router.post("/settings/preferences")
async def update_preferences(
    request: Request,
    bio: str = Form(""),
    favorite_genre: str = Form(""),
    favorite_book: str = Form(""),
    favorite_author: str = Form(""),
    db: Session = Depends(get_db),
):
    """Update bio and favorites."""
    user = require_current_user(request, db)
    user.bio = bio.strip() or None
    user.favorite_genre = favorite_genre.strip() or None
    user.favorite_book = favorite_book.strip() or None
    user.favorite_author = favorite_author.strip() or None
    db.commit()
    request.session["flash_message"] = "Preferences updated."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/profile/settings", status_code=303)


@router.post("/settings/privacy")
async def update_privacy(
    request: Request,
    db: Session = Depends(get_db),
):
    """Update per-field privacy toggles (checkboxes)."""
    user = require_current_user(request, db)
    form = await request.form()
    user.bio_public = "bio_public" in form
    user.favorites_public = "favorites_public" in form
    user.reading_history_public = "reading_history_public" in form
    db.commit()
    request.session["flash_message"] = "Privacy settings updated."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/profile/settings", status_code=303)


@router.post("/settings/clubs")
async def update_club_visibility(
    request: Request,
    db: Session = Depends(get_db),
):
    """Update per-club profile visibility."""
    user = require_current_user(request, db)
    form = await request.form()
    for member in user.members:
        member.profile_visible = f"visible_{member.id}" in form
    db.commit()
    request.session["flash_message"] = "Club visibility updated."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/profile/settings", status_code=303)


@router.post("/settings/delete")
async def delete_account(
    request: Request,
    confirm_username: str = Form(...),
    db: Session = Depends(get_db),
):
    """Permanently delete the account after username confirmation."""
    user = require_current_user(request, db)

    if confirm_username.strip() != user.username:
        request.session["flash_message"] = "Username did not match. Account not deleted."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/profile/settings", status_code=303)

    # Clear rows that reference members.id without a cascade relationship
    for member in user.members:
        db.query(Book).filter(Book.suggested_by == member.id).update({"suggested_by": None})
        for model in [
            Rating, BookVote, MeetingRSVP, ReviewLike, ReviewComment,
            ReviewCommentLike, DiscussionPostLike, DiscussionCommentLike,
        ]:
            db.query(model).filter(model.member_id == member.id).delete()

    db.delete(user)
    db.commit()

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# Public profile view
# ---------------------------------------------------------------------------

@router.get("/{username}", response_class=HTMLResponse)
async def view_profile(
    request: Request,
    username: str,
    db: Session = Depends(get_db),
):
    """View a user's profile. Requires login."""
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    profile_user = db.query(User).filter(User.username == username).first()
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    is_own_profile = current_user.id == profile_user.id

    reading_history = (
        _get_reading_history(profile_user, db)
        if profile_user.reading_history_public
        else []
    )

    visible_clubs = [
        m.club for m in profile_user.members if m.profile_visible
    ]

    stats = _get_stats(profile_user)

    return templates.TemplateResponse(
        "profile/view.html",
        {
            "request": request,
            "title": f"{profile_user.display_name or profile_user.username}'s Profile",
            "current_user": current_user,
            "profile_user": profile_user,
            "is_own_profile": is_own_profile,
            "reading_history": reading_history,
            "visible_clubs": visible_clubs,
            "stats": stats,
        },
    )
