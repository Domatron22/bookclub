from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import secrets

from ..database import get_db
from ..models import Club, Member, Meeting, MeetingSchedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/create", response_class=HTMLResponse)
async def create_club_form(request: Request):
    """Render club creation form"""
    return templates.TemplateResponse(
        "clubs/create.html",
        {"request": request, "title": "Create a Book Club"}
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
    
    # Generate new session ID for this club membership
    session_id = secrets.token_urlsafe(32)
    
    # Auto-join the creator as a member with their chosen display name
    member = Member(
        club_id=club.id,
        display_name=display_name,
        session_id=session_id,
        is_admin=True  # Creator is automatically admin
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    
    # Set cookie and redirect
    response = RedirectResponse(
        url=f"/clubs/{club.code}",
        status_code=303
    )
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=30*24*60*60  # 30 days
    )
    return response


@router.get("/join", response_class=HTMLResponse)
async def join_club_form(request: Request):
    """Render club join form"""
    return templates.TemplateResponse(
        "clubs/join.html",
        {"request": request, "title": "Join a Book Club"}
    )


@router.post("/join")
async def join_club(
    request: Request,
    code: str = Form(...),
    display_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Join a club with a code"""
    # Find club
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Generate session ID
    session_id = secrets.token_urlsafe(32)
    
    # Create member
    member = Member(
        club_id=club.id,
        display_name=display_name,
        session_id=session_id
    )
    db.add(member)
    db.commit()
    
    # Set session cookie and redirect
    response = RedirectResponse(
        url=f"/clubs/{club.code}",
        status_code=303
    )
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=30*24*60*60  # 30 days
    )
    return response


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
    
    # Get current member if authenticated
    session_id = request.cookies.get("session_id")
    current_member = None
    if session_id:
        current_member = db.query(Member).filter(
            Member.session_id == session_id,
            Member.club_id == club.id
        ).first()
    
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
    
    return templates.TemplateResponse(
        "clubs/view.html",
        {
            "request": request,
            "title": club.name,
            "club": club,
            "current_member": current_member,
            "suggested_books": suggested_books,
            "current_book": current_book,
            "completed_books": completed_books,
            "next_meeting": next_meeting,
            "datetime": datetime
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
    
    # Get current member
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    member = db.query(Member).filter(
        Member.session_id == session_id,
        Member.club_id == club.id
    ).first()
    
    if member:
        # Delete the member
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
    
    # Get current member
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    current_member = db.query(Member).filter(
        Member.session_id == session_id,
        Member.club_id == club.id
    ).first()
    
    if not current_member or not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get flash message if exists
    flash_message = request.session.pop('flash_message', None)
    flash_type = request.session.pop('flash_type', 'info')
    
    return templates.TemplateResponse(
        "clubs/admin.html",
        {
            "request": request,
            "title": f"Admin Settings - {club.name}",
            "club": club,
            "current_member": current_member,
            "flash_message": flash_message,
            "flash_type": flash_type
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
    
    # Verify admin
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    current_member = db.query(Member).filter(
        Member.session_id == session_id,
        Member.club_id == club.id
    ).first()
    
    if not current_member or not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Update settings
    club.veto_enabled = veto_enabled
    club.veto_percentage = max(1, min(100, veto_percentage))
    club.book_selection_method = book_selection_method
    club.voting_percentage = max(1, min(100, voting_percentage))
    
    db.commit()
    
    # Set flash message
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
    
    # Verify current user is admin
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    current_member = db.query(Member).filter(
        Member.session_id == session_id,
        Member.club_id == club.id
    ).first()
    
    if not current_member or not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Promote member
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.club_id == club.id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    member.is_admin = True
    db.commit()
    
    # Set flash message
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
    
    # Verify current user is admin
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    current_member = db.query(Member).filter(
        Member.session_id == session_id,
        Member.club_id == club.id
    ).first()
    
    if not current_member or not current_member.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Demote member
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.club_id == club.id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    # Count admins
    admin_count = db.query(Member).filter(
        Member.club_id == club.id,
        Member.is_admin == True
    ).count()
    
    # Don't allow demoting the last admin
    if admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot demote the last admin")
    
    member.is_admin = False
    db.commit()
    
    # Set flash message
    request.session['flash_message'] = f"{member.display_name} removed as admin"
    request.session['flash_type'] = "success"
    
    return RedirectResponse(url=f"/clubs/{club.code}/admin", status_code=303)