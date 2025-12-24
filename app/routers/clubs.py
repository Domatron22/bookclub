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
        session_id=session_id
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