from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import pytz

from ..database import get_db
from ..dependencies import get_current_user, require_current_user, get_member_for_club, require_member_for_club
from ..models import Meeting, MeetingSchedule, Club, Member, Book, MeetingRSVP

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/club/{club_code}", response_class=HTMLResponse)
async def view_meetings(
    request: Request,
    club_code: str,
    db: Session = Depends(get_db)
):
    """View all meetings for a club in calendar format"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = get_current_user(request, db)
    current_member = get_member_for_club(user, club.id, db)

    upcoming_meetings = db.query(Meeting).filter(
        Meeting.club_id == club.id,
        Meeting.status == "scheduled",
        Meeting.meeting_datetime >= datetime.utcnow()
    ).order_by(Meeting.meeting_datetime).all()

    past_meetings = db.query(Meeting).filter(
        Meeting.club_id == club.id,
        Meeting.status.in_(["completed", "cancelled"]),
    ).order_by(Meeting.meeting_datetime.desc()).limit(10).all()

    return templates.TemplateResponse(
        "meetings/calendar.html",
        {
            "request": request,
            "title": f"Meetings - {club.name}",
            "club": club,
            "current_user": user,
            "current_member": current_member,
            "upcoming_meetings": upcoming_meetings,
            "past_meetings": past_meetings,
            "meeting_schedule": club.meeting_schedule,
        }
    )


@router.get("/setup/{club_code}", response_class=HTMLResponse)
async def setup_schedule_form(
    request: Request,
    club_code: str,
    db: Session = Depends(get_db)
):
    """Show form to setup meeting schedule"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, club.id, db)

    if club.meeting_schedule and club.meeting_schedule.current_host_id != member.id:
        raise HTTPException(status_code=403, detail="Only the current host can modify the schedule")

    return templates.TemplateResponse(
        "meetings/setup.html",
        {
            "request": request,
            "title": f"Setup Meeting Schedule - {club.name}",
            "club": club,
            "current_user": user,
            "current_member": member,
            "schedule": club.meeting_schedule,
        }
    )


@router.post("/setup/{club_code}")
async def setup_schedule(
    request: Request,
    club_code: str,
    recurrence_pattern: str = Form(...),
    recurrence_details: str = Form(...),
    default_duration_minutes: int = Form(120),
    db: Session = Depends(get_db)
):
    """Create or update meeting schedule for a club"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, club.id, db)

    if club.meeting_schedule:
        if club.meeting_schedule.current_host_id != member.id:
            raise HTTPException(status_code=403, detail="Only the current host can modify the schedule")
        club.meeting_schedule.recurrence_pattern = recurrence_pattern
        club.meeting_schedule.recurrence_details = recurrence_details
        club.meeting_schedule.default_duration_minutes = default_duration_minutes
    else:
        schedule = MeetingSchedule(
            club_id=club.id,
            current_host_id=member.id,
            recurrence_pattern=recurrence_pattern,
            recurrence_details=recurrence_details,
            default_duration_minutes=default_duration_minutes
        )
        db.add(schedule)

    db.commit()

    return RedirectResponse(url=f"/meetings/club/{club.code}", status_code=303)


@router.get("/create/{club_code}", response_class=HTMLResponse)
async def create_meeting_form(
    request: Request,
    club_code: str,
    db: Session = Depends(get_db)
):
    """Show form to create a new meeting"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, club.id, db)

    if club.meeting_schedule and club.meeting_schedule.current_host_id != member.id:
        raise HTTPException(status_code=403, detail="Only the current host can schedule meetings")

    current_book = next((b for b in club.books if b.status == "reading"), None)
    all_books = club.books

    return templates.TemplateResponse(
        "meetings/create.html",
        {
            "request": request,
            "title": f"Schedule Meeting - {club.name}",
            "club": club,
            "current_user": user,
            "current_member": member,
            "schedule": club.meeting_schedule,
            "current_book": current_book,
            "all_books": all_books,
            "datetime": datetime,
        }
    )


@router.post("/create/{club_code}")
async def create_meeting(
    request: Request,
    club_code: str,
    title: str = Form(...),
    meeting_date: str = Form(...),
    meeting_time: str = Form(...),
    duration_minutes: int = Form(120),
    location: str = Form(""),
    description: str = Form(""),
    book_id: int = Form(None),
    db: Session = Depends(get_db)
):
    """Create a new meeting"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, club.id, db)

    if club.meeting_schedule and club.meeting_schedule.current_host_id != member.id:
        raise HTTPException(status_code=403, detail="Only the current host can schedule meetings")

    meeting_datetime = datetime.strptime(f"{meeting_date} {meeting_time}", "%Y-%m-%d %H:%M")

    meeting = Meeting(
        club_id=club.id,
        host_id=member.id,
        book_id=book_id if book_id else None,
        title=title,
        description=description,
        meeting_datetime=meeting_datetime,
        duration_minutes=duration_minutes,
        location=location,
        status="scheduled"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    host_rsvp = MeetingRSVP(
        meeting_id=meeting.id,
        member_id=member.id,
        status="yes",
        bringing="",
        notes="Host"
    )
    db.add(host_rsvp)
    db.commit()

    return RedirectResponse(url=f"/meetings/club/{club.code}", status_code=303)


@router.post("/{meeting_id}/complete")
async def complete_meeting(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
):
    """Mark a meeting as completed"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    user = require_current_user(request, db)
    require_member_for_club(user, meeting.club_id, db)

    meeting.status = "completed"
    meeting.completed_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(
        url=f"/meetings/create/{meeting.club.code}?from_completed={meeting_id}",
        status_code=303
    )


@router.post("/{meeting_id}/cancel")
async def cancel_meeting(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a meeting"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, meeting.club_id, db)

    if meeting.host_id != member.id:
        raise HTTPException(status_code=403, detail="Only the host can cancel this meeting")

    meeting.status = "cancelled"
    db.commit()

    return RedirectResponse(url=f"/meetings/club/{meeting.club.code}", status_code=303)


@router.post("/transfer-host/{club_code}")
async def transfer_host(
    request: Request,
    club_code: str,
    new_host_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Transfer host privileges to another member"""
    club = db.query(Club).filter(Club.code == club_code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, club.id, db)

    if not club.meeting_schedule or club.meeting_schedule.current_host_id != member.id:
        raise HTTPException(status_code=403, detail="Only the current host can transfer host privileges")

    new_host = db.query(Member).filter(
        Member.id == new_host_id,
        Member.club_id == club.id
    ).first()
    if not new_host:
        raise HTTPException(status_code=404, detail="New host not found in this club")

    club.meeting_schedule.current_host_id = new_host_id
    db.commit()

    return RedirectResponse(url=f"/meetings/club/{club.code}", status_code=303)


@router.get("/{meeting_id}/download.ics")
async def download_meeting_ics(
    meeting_id: int,
    db: Session = Depends(get_db)
):
    """Generate and download ICS calendar file for a meeting"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    cal = Calendar()
    cal.add('prodid', '-//Coverbound Meeting//EN')
    cal.add('version', '2.0')

    event = Event()
    event.add('summary', meeting.title)
    event.add('dtstart', meeting.meeting_datetime)
    event.add('dtend', meeting.meeting_datetime + timedelta(minutes=meeting.duration_minutes))

    if meeting.location:
        event.add('location', meeting.location)

    if meeting.description:
        event.add('description', meeting.description)

    event.add('status', 'CONFIRMED' if meeting.status == 'scheduled' else 'CANCELLED')

    cal.add_component(event)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=meeting_{meeting.id}.ics"}
    )


@router.get("/{meeting_id}/rsvp", response_class=HTMLResponse)
async def rsvp_form(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
):
    """Show RSVP form with list of what others are bringing"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, meeting.club_id, db)

    current_rsvp = db.query(MeetingRSVP).filter(
        MeetingRSVP.meeting_id == meeting_id,
        MeetingRSVP.member_id == member.id
    ).first()

    all_rsvps = db.query(MeetingRSVP).filter(
        MeetingRSVP.meeting_id == meeting_id,
        MeetingRSVP.status == "yes"
    ).all()

    return templates.TemplateResponse(
        "meetings/rsvp.html",
        {
            "request": request,
            "title": f"RSVP - {meeting.title}",
            "meeting": meeting,
            "club": meeting.club,
            "current_user": user,
            "current_member": member,
            "current_rsvp": current_rsvp,
            "all_rsvps": all_rsvps,
        }
    )


@router.post("/{meeting_id}/rsvp")
async def submit_rsvp(
    request: Request,
    meeting_id: int,
    status: str = Form(...),
    bringing: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """Submit or update RSVP for a meeting"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, meeting.club_id, db)

    rsvp = db.query(MeetingRSVP).filter(
        MeetingRSVP.meeting_id == meeting_id,
        MeetingRSVP.member_id == member.id
    ).first()

    if rsvp:
        rsvp.status = status
        rsvp.bringing = bringing
        rsvp.notes = notes
        rsvp.updated_at = datetime.utcnow()
    else:
        rsvp = MeetingRSVP(
            meeting_id=meeting_id,
            member_id=member.id,
            status=status,
            bringing=bringing,
            notes=notes
        )
        db.add(rsvp)

    db.commit()

    return RedirectResponse(url=f"/clubs/{meeting.club.code}", status_code=303)
