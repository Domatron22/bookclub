from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..dependencies import (
    get_current_user,
    require_current_user,
    get_member_for_club,
    require_member_for_club,
)
from ..models import Club, Member, Meeting, MeetingSchedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/create", response_class=HTMLResponse)
async def create_club_form(request: Request, db: Session = Depends(get_db)):
    """Render club creation form"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        "clubs/create.html",
        {"request": request, "title": "Create a Book Club", "current_user": user}
    )


@router.post("/create")
async def create_club(
    request: Request,
    name: str = Form(...),
    display_name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Create a new book club"""
    user = require_current_user(request, db)

    # Generate unique club code
    code = Club.generate_code()
    while db.query(Club).filter(Club.code == code).first():
        code = Club.generate_code()

    # Create club
    club = Club(
        name=name,
        code=code,
        description=description
    )
    db.add(club)
    db.commit()
    db.refresh(club)

    # Auto-join the creator as admin member
    member = Member(
        club_id=club.id,
        user_id=user.id,
        display_name=display_name,
        is_admin=True
    )
    db.add(member)
    db.commit()

    return RedirectResponse(url=f"/clubs/{club.code}", status_code=303)


@router.get("/join", response_class=HTMLResponse)
async def join_club_form(request: Request, db: Session = Depends(get_db)):
    """Render club join form"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        "clubs/join.html",
        {"request": request, "title": "Join a Book Club", "current_user": user}
    )


@router.post("/join")
async def join_club(
    request: Request,
    code: str = Form(...),
    display_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Join a club with a code"""
    user = require_current_user(request, db)

    # Find club
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Check if already a member
    existing = get_member_for_club(user, club.id, db)
    if existing:
        return RedirectResponse(url=f"/clubs/{club.code}", status_code=303)

    # Create member
    member = Member(
        club_id=club.id,
        user_id=user.id,
        display_name=display_name
    )
    db.add(member)
    db.commit()

    return RedirectResponse(url=f"/clubs/{club.code}", status_code=303)


@router.get("/{code}", response_class=HTMLResponse)
async def view_club(
    request: Request,
    code: str,
    db: Session = Depends(get_db)
):
    """View club details"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = get_current_user(request, db)
    current_member = get_member_for_club(user, club.id, db)

    # Get books in different states
    suggested_books = [b for b in club.books if b.status == "suggested" and not b.vetoed]
    current_book = next((b for b in club.books if b.status == "reading"), None)
    completed_books = [b for b in club.books if b.status == "completed"]

    # Get next upcoming meeting
    next_meeting = db.query(Meeting).filter(
        Meeting.club_id == club.id,
        Meeting.status == "scheduled",
        Meeting.meeting_datetime >= datetime.utcnow()
    ).order_by(Meeting.meeting_datetime).first()

    # Flash messages
    flash_message = request.session.pop('flash_message', None)
    flash_type = request.session.pop('flash_type', 'info')

    return templates.TemplateResponse(
        "clubs/view.html",
        {
            "request": request,
            "title": club.name,
            "club": club,
            "current_user": user,
            "current_member": current_member,
            "suggested_books": suggested_books,
            "current_book": current_book,
            "completed_books": completed_books,
            "next_meeting": next_meeting,
            "flash_message": flash_message,
            "flash_type": flash_type,
            "datetime": datetime,
        }
    )


@router.post("/{code}/leave")
async def leave_club(
    request: Request,
    code: str,
    db: Session = Depends(get_db)
):
    """Leave a club"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = get_member_for_club(user, club.id, db)

    if member:
        db.delete(member)
        db.commit()

    return RedirectResponse(url="/", status_code=303)


@router.get("/{code}/admin", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    code: str,
    db: Session = Depends(get_db)
):
    """View admin settings page"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    current_member = require_member_for_club(user, club.id, db)

    if not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    flash_message = request.session.pop('flash_message', None)
    flash_type = request.session.pop('flash_type', 'info')

    return templates.TemplateResponse(
        "clubs/admin.html",
        {
            "request": request,
            "title": f"Admin Settings - {club.name}",
            "club": club,
            "current_user": user,
            "current_member": current_member,
            "flash_message": flash_message,
            "flash_type": flash_type,
        }
    )


@router.post("/{code}/admin/settings")
async def update_settings(
    request: Request,
    code: str,
    veto_enabled: bool = Form(False),
    veto_percentage: int = Form(50),
    book_selection_method: str = Form("random"),
    voting_percentage: int = Form(50),
    db: Session = Depends(get_db)
):
    """Update club settings"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    current_member = require_member_for_club(user, club.id, db)

    if not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    club.veto_enabled = veto_enabled
    club.veto_percentage = max(1, min(100, veto_percentage))
    club.book_selection_method = book_selection_method
    club.voting_percentage = max(1, min(100, voting_percentage))
    db.commit()

    request.session['flash_message'] = "Settings updated successfully!"
    request.session['flash_type'] = "success"

    return RedirectResponse(url=f"/clubs/{club.code}/admin", status_code=303)


@router.post("/{code}/admin/promote")
async def promote_member(
    request: Request,
    code: str,
    member_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Promote a member to admin"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    current_member = require_member_for_club(user, club.id, db)

    if not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    member = db.query(Member).filter(
        Member.id == member_id,
        Member.club_id == club.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member.is_admin = True
    db.commit()

    request.session['flash_message'] = f"{member.display_name} promoted to admin!"
    request.session['flash_type'] = "success"

    return RedirectResponse(url=f"/clubs/{club.code}/admin", status_code=303)


@router.post("/{code}/admin/demote")
async def demote_member(
    request: Request,
    code: str,
    member_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Demote an admin to regular member"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    current_member = require_member_for_club(user, club.id, db)

    if not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    member = db.query(Member).filter(
        Member.id == member_id,
        Member.club_id == club.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    admin_count = db.query(Member).filter(
        Member.club_id == club.id,
        Member.is_admin == True
    ).count()

    if admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot demote the last admin")

    member.is_admin = False
    db.commit()

    request.session['flash_message'] = f"{member.display_name} removed as admin"
    request.session['flash_type'] = "success"

    return RedirectResponse(url=f"/clubs/{club.code}/admin", status_code=303)
