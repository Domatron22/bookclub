# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..dependencies import (
    get_current_user,
    require_current_user,
    get_member_for_club,
    require_club_admin,
    require_member_for_club,
)
from ..models import Club, Member, Meeting, MeetingSchedule
from ..templating import templates, base_context
from ..recaps import club_recap
from .. import selection

router = APIRouter()


@router.get("/create", response_class=HTMLResponse)
async def create_club_form(request: Request, db: Session = Depends(get_db)):
    """Render club creation form"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "clubs/create.html",
        {**base_context(request, db, user), "title": "Create a Book Club"}
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

    # A brand-new club has nothing to show yet — land on the empty state,
    # which walks the creator through inviting people and picking a first book.
    return RedirectResponse(url=f"/clubs/{club.code}/welcome", status_code=303)


@router.get("/join", response_class=HTMLResponse)
async def join_club_form(request: Request, code: str = "", db: Session = Depends(get_db)):
    """Render club join form"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Offer the directory to anyone who arrived without a code — but only when
    # something is listed in it.
    total_public = db.query(Club).filter(Club.is_public == True).count()  # noqa: E712

    return templates.TemplateResponse(
        request,
        "clubs/join.html",
        {
            **base_context(request, db, user),
            "title": "Join a Book Club",
            "total_public": total_public,
            # Prefilled when someone followed a club link they can't open yet.
            "code": code.strip().upper()[:8],
        },
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


@router.get("/browse", response_class=HTMLResponse)
async def browse_clubs(request: Request, q: str = "", db: Session = Depends(get_db)):
    """Public directory of clubs whose admin opted into listing.

    Declared before `/{code}` so the literal path wins the match. Open to
    logged-out visitors — that is the point of the directory — but it only ever
    exposes what a club chose to publish: name, description and headline counts.
    """
    user = get_current_user(request, db)

    clubs = (
        db.query(Club)
        .filter(Club.is_public == True)  # noqa: E712
        .order_by(Club.name)
        .all()
    )

    term = q.strip().lower()
    if term:
        clubs = [
            c for c in clubs
            if term in (c.name or "").lower() or term in (c.description or "").lower()
        ]

    my_club_ids = {m.club_id for m in user.members} if user else set()

    rows = []
    for c in clubs:
        rows.append({
            "club": c,
            "reading": next((b for b in c.books if b.status == "reading"), None),
            "members": len(c.members),
            "books_read": len([b for b in c.books if b.status == "completed"]),
            "is_member": c.id in my_club_ids,
        })

    total_public = db.query(Club).filter(Club.is_public == True).count()  # noqa: E712

    return templates.TemplateResponse(
        request,
        "clubs/browse.html",
        {
            **base_context(request, db, user, screen="browse"),
            "title": "Browse clubs",
            "rows": rows,
            "query": q,
            "total_public": total_public,
        },
    )


def _send_to_join(request: Request, club: Club) -> RedirectResponse:
    """Point a signed-in non-member at the join form rather than a bare 403.

    They followed a real club link; the only thing missing is membership, and
    the code is already in the URL they used.
    """
    request.session['flash_message'] = (
        f"“{club.name}” is members only. Join with the club code to take part."
    )
    request.session['flash_type'] = "info"
    return RedirectResponse(url=f"/clubs/join?code={club.code}", status_code=303)


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

    # Everything below — the shelf, reviews, who has read how far — belongs to
    # the club's members. The public directory carries the listing instead.
    user = require_current_user(request, db)
    current_member = get_member_for_club(user, club.id, db)
    if not current_member:
        return _send_to_join(request, club)

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

    # "The shelf so far" marquee interleaves each finished book's cover with a
    # standout review of it, so the strip alternates cover → review → cover.
    shelf_items = []
    for book in sorted(completed_books, key=lambda b: b.completed_at or datetime.min, reverse=True):
        shelf_items.append({"kind": "cover", "book": book})
        reviewed = [r for r in book.ratings if (r.review or "").strip()]
        if reviewed:
            shelf_items.append({
                "kind": "review",
                "book": book,
                "rating": max(reviewed, key=lambda r: r.rating),
            })

    # Per-member reading progress on the current book.
    member_progress, my_progress, finished_count = [], None, 0
    if current_book and club.feature_progress:
        pages = current_book.page_count or 0
        by_member = {p.member_id: p for p in current_book.progress_entries}
        done_ids = {c.member_id for c in current_book.completions}

        for m in club.members:
            entry = by_member.get(m.id)
            page = entry.page if entry else 0
            done = m.id in done_ids or (pages and page >= pages)
            if done:
                finished_count += 1
            member_progress.append({
                "name": m.display_name,
                "page": page,
                "done": done,
                "percent": min(100, round(page / pages * 100)) if pages else 0,
            })
            if current_member and m.id == current_member.id:
                my_progress = member_progress[-1]

    # Flash messages
    flash_message = request.session.pop('flash_message', None)
    flash_type = request.session.pop('flash_type', 'info')

    return templates.TemplateResponse(
        request,
        "clubs/view.html",
        {
            **base_context(request, db, user, club=club),
            "title": club.name,
            "club": club,
            "current_member": current_member,
            "suggested_books": suggested_books,
            "current_book": current_book,
            "completed_books": completed_books,
            "shelf_items": shelf_items,
            "member_progress": member_progress,
            "my_progress": my_progress,
            "finished_count": finished_count,
            "recap_year": datetime.utcnow().year,
            "next_meeting": next_meeting,
            "flash_message": flash_message,
            "flash_type": flash_type,
            "datetime": datetime,
        }
    )


@router.get("/{code}/shelf", response_class=HTMLResponse)
async def view_shelf(request: Request, code: str, db: Session = Depends(get_db)):
    """Every book this club has finished, newest first."""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    current_member = get_member_for_club(user, club.id, db)
    if not current_member:
        return _send_to_join(request, club)

    finished = sorted(
        [b for b in club.books if b.status == "completed"],
        key=lambda b: b.completed_at or datetime.min,
        reverse=True,
    )

    shelf = []
    for book in finished:
        scores = [r.rating for r in book.ratings]
        shelf.append({
            "book": book,
            "avg": round(sum(scores) / len(scores), 1) if scores else None,
            "reviews": len(scores),
            "discussions": len(book.discussions),
        })

    return templates.TemplateResponse(
        request,
        "clubs/shelf.html",
        {
            **base_context(request, db, user, club=club),
            "title": f"The shelf — {club.name}",
            "club": club,
            "current_member": current_member,
            "shelf": shelf,
        },
    )


@router.get("/{code}/recap", response_class=HTMLResponse)
async def club_year_in_books(request: Request, code: str, db: Session = Depends(get_db)):
    """The club's year in books."""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if not club.feature_recap:
        raise HTTPException(status_code=404, detail="This club's recap is turned off")

    user = require_current_user(request, db)
    require_member_for_club(user, club.id, db)

    year = request.query_params.get("year")
    recap = club_recap(club, int(year) if year and year.isdigit() else None)

    return templates.TemplateResponse(
        request,
        "recap.html",
        {
            **base_context(request, db, user, club=club),
            "title": f"{recap['year']} in books — {club.name}",
            "club": club,
            "recap": recap,
            "back_href": f"/clubs/{club.code}",
            "back_label": "Back to club",
        },
    )


def _votes_needed(club: Club) -> int:
    """How many upvotes carry a book, given the club's threshold.

    Ceiling division: at 50% of three members, two votes carry it, not one and
    a half. Always at least one, so a book can never win on no votes at all.
    """
    total_voters = len(club.members)
    return max(1, -(-total_voters * club.voting_percentage // 100))


@router.get("/{code}/select", response_class=HTMLResponse)
async def choose_next_book(request: Request, code: str, db: Session = Depends(get_db)):
    """Pick the club's next read — by vote or by chance, per club settings."""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    current_member = require_member_for_club(user, club.id, db)

    candidates = [b for b in club.books if b.status == "suggested" and not b.vetoed]
    total_voters = len(club.members)

    books = []
    my_vote = None
    for book in candidates:
        upvotes = [v for v in book.votes if v.vote_type == "upvote"]
        vetoes = [v for v in book.votes if v.vote_type == "veto"]
        mine = any(v.member_id == current_member.id for v in upvotes)
        if mine:
            my_vote = book.id
        books.append({
            "book": book,
            "count": len(upvotes),
            "percent": round(len(upvotes) / total_voters * 100) if total_voters else 0,
            "mine": mine,
            "vetoed": any(v.member_id == current_member.id for v in vetoes),
            "veto_count": len(vetoes),
        })

    max_count = max((b["count"] for b in books), default=0)
    for b in books:
        b["leading"] = b["count"] == max_count and b["count"] > 0

    # Set after an admin closes voting, so the same acknowledgment modal the
    # random reel uses also confirms a vote-decided winner.
    picked_id = request.query_params.get("picked")
    picked = next((b for b in candidates if str(b.id) == picked_id), None)

    return templates.TemplateResponse(
        request,
        "clubs/select.html",
        {
            **base_context(request, db, user, club=club),
            "title": f"Choose next book — {club.name}",
            "club": club,
            "current_member": current_member,
            "books": books,
            "my_vote": my_vote,
            "total_voters": total_voters,
            "votes_needed": _votes_needed(club),
            "already_reading": any(b.status == "reading" for b in club.books),
            "picked": picked,
        },
    )


@router.post("/{code}/close-voting")
async def close_voting(request: Request, code: str, db: Session = Depends(get_db)):
    """Admin closes voting; the leading title becomes the next read."""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    require_club_admin(user, club.id, db)

    candidates = [b for b in club.books if b.status == "suggested" and not b.vetoed]
    if not candidates:
        request.session['flash_message'] = "No books are in the running."
        request.session['flash_type'] = "error"
        return RedirectResponse(url=f"/clubs/{club.code}/select", status_code=303)

    def upvotes(book):
        return len([v for v in book.votes if v.vote_type == "upvote"])

    needed = _votes_needed(club)
    top = max(upvotes(b) for b in candidates)

    if top < needed:
        request.session['flash_message'] = (
            f"No book has reached {needed} vote{'' if needed == 1 else 's'} yet — "
            f"the best so far has {top}. Leave voting open, or lower the threshold "
            "in club settings."
        )
        request.session['flash_type'] = "error"
        return RedirectResponse(url=f"/clubs/{club.code}/select", status_code=303)

    leaders = [b for b in candidates if upvotes(b) == top]
    if len(leaders) > 1:
        # Picking one arbitrarily would look like the club decided when it
        # hasn't. Say so and let the members break it.
        titles = ", ".join(f"“{b.title}”" for b in leaders)
        request.session['flash_message'] = (
            f"It's a tie on {top} vote{'' if top == 1 else 's'}: {titles}. "
            "Ask someone to change their vote, then close again."
        )
        request.session['flash_type'] = "error"
        return RedirectResponse(url=f"/clubs/{club.code}/select", status_code=303)

    winner = leaders[0]
    # Remembered server-side so the acknowledgment step can only commit this
    # book — `?picked=` is just a number in a URL the caller controls.
    selection.remember(request, club.id, winner.id)
    return RedirectResponse(url=f"/clubs/{club.code}/select?picked={winner.id}", status_code=303)


@router.get("/{code}/welcome", response_class=HTMLResponse)
async def club_welcome(request: Request, code: str, db: Session = Depends(get_db)):
    """Empty state shown right after a club is created."""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    require_member_for_club(user, club.id, db)

    return templates.TemplateResponse(
        request,
        "clubs/welcome.html",
        {
            **base_context(request, db, user, club=club),
            "title": f"Welcome to {club.name}",
            "club": club,
        },
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

    if not member:
        return RedirectResponse(url="/", status_code=303)

    # A club with no admin can never be configured again, and nobody can
    # promote a replacement. Make them hand it over first.
    if member.is_admin:
        other_admins = db.query(Member).filter(
            Member.club_id == club.id,
            Member.is_admin == True,  # noqa: E712
            Member.id != member.id,
        ).count()
        if not other_admins and len(club.members) > 1:
            request.session['flash_message'] = (
                "You're the only admin. Promote someone else before you leave, "
                "so the club isn't left without one."
            )
            request.session['flash_type'] = "error"
            return RedirectResponse(url=f"/clubs/{club.code}/admin", status_code=303)

    # The member's posts, votes, ratings and progress go with them; their book
    # suggestions stay on the shortlist, unattributed.
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
    current_member = require_club_admin(user, club.id, db)

    flash_message = request.session.pop('flash_message', None)
    flash_type = request.session.pop('flash_type', 'info')

    return templates.TemplateResponse(
        request,
        "clubs/admin.html",
        {
            **base_context(request, db, user, club=club),
            "title": f"Admin Settings - {club.name}",
            "club": club,
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
    votes_visible: bool = Form(False),
    is_public: bool = Form(False),
    feature_progress: bool = Form(False),
    feature_recap: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Update club settings"""
    club = db.query(Club).filter(Club.code == code.upper()).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    user = require_current_user(request, db)
    require_club_admin(user, club.id, db)

    club.veto_enabled = veto_enabled
    club.veto_percentage = max(1, min(100, veto_percentage))
    club.book_selection_method = book_selection_method
    club.voting_percentage = max(1, min(100, voting_percentage))
    club.votes_visible = votes_visible
    club.is_public = is_public
    club.feature_progress = feature_progress
    club.feature_recap = feature_recap
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
    require_club_admin(user, club.id, db)

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
    require_club_admin(user, club.id, db)

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
