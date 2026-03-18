from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .models import Member, User

COOKIE_NAME = "coverbound_user_id"


def get_current_user(request: Request, db: Session) -> "User | None":
    """Read the coverbound_user_id cookie and return the User, or None if not authenticated."""
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        uid = int(raw)
    except (ValueError, TypeError):
        return None
    user = db.query(User).filter(User.id == uid).first()
    if user:
        user.last_seen_at = datetime.utcnow()
        db.commit()
    return user


def require_current_user(request: Request, db: Session) -> User:
    """Like get_current_user but raises 401 if not authenticated."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_member_for_club(user: "User | None", club_id: int, db: Session) -> "Member | None":
    """Return the Member record for (user_id, club_id), or None."""
    if not user:
        return None
    return db.query(Member).filter(
        Member.user_id == user.id,
        Member.club_id == club_id
    ).first()


def require_member_for_club(user: "User | None", club_id: int, db: Session) -> Member:
    """Like get_member_for_club but raises 403 if not a member."""
    member = get_member_for_club(user, club_id, db)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    return member
