from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Discussion, DiscussionPost, DiscussionPostLike, DiscussionPostReply, Book, Member

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
async def view_discussions(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db)
):
    """View all discussions for a book"""
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
    
    return templates.TemplateResponse(
        "discussions/list.html",
        {
            "request": request,
            "title": f"Discussions - {book.title}",
            "book": book,
            "club": book.club,
            "current_member": current_member,
            "discussions": book.discussions
        }
    )


@router.post("/create")
async def create_discussion(
    request: Request,
    book_id: int = Form(...),
    title: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create a new discussion thread"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Verify member
    member = get_current_member(request, db)
    if member.club_id != book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    discussion = Discussion(
        book_id=book_id,
        title=title
    )
    db.add(discussion)
    db.commit()
    
    return RedirectResponse(
        url=f"/discussions/{discussion.id}",
        status_code=303
    )


@router.get("/{discussion_id}", response_class=HTMLResponse)
async def view_discussion(
    request: Request,
    discussion_id: int,
    db: Session = Depends(get_db)
):
    """View a discussion thread"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # Get current member
    session_id = request.cookies.get("session_id")
    current_member = None
    if session_id:
        current_member = db.query(Member).filter(
            Member.session_id == session_id,
            Member.club_id == discussion.book.club_id
        ).first()
    
    return templates.TemplateResponse(
        "discussions/view.html",
        {
            "request": request,
            "title": discussion.title,
            "discussion": discussion,
            "book": discussion.book,
            "club": discussion.book.club,
            "current_member": current_member
        }
    )


@router.post("/{discussion_id}/post")
async def add_post(
    request: Request,
    discussion_id: int,
    content: str = Form(...),
    is_spoiler: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Add a post to a discussion"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # Verify member
    member = get_current_member(request, db)
    if member.club_id != discussion.book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    post = DiscussionPost(
        discussion_id=discussion_id,
        author_id=member.id,
        content=content,
        is_spoiler=is_spoiler
    )
    db.add(post)
    db.commit()
    
    return RedirectResponse(
        url=f"/discussions/{discussion_id}",
        status_code=303
    )


@router.post("/post/{post_id}/like")
async def like_post(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db)
):
    """Like or unlike a discussion post"""
    post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    member = get_current_member(request, db)
    if member.club_id != post.discussion.book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Check if already liked
    existing_like = db.query(DiscussionPostLike).filter(
        DiscussionPostLike.post_id == post_id,
        DiscussionPostLike.member_id == member.id
    ).first()
    
    if existing_like:
        # Unlike
        db.delete(existing_like)
    else:
        # Like
        like = DiscussionPostLike(
            post_id=post_id,
            member_id=member.id
        )
        db.add(like)
    
    db.commit()
    
    return RedirectResponse(
        url=f"/discussions/{post.discussion_id}",
        status_code=303
    )


@router.post("/post/{post_id}/reply")
async def reply_to_post(
    request: Request,
    post_id: int,
    content: str = Form(...),
    is_spoiler: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Reply to a discussion post"""
    post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    member = get_current_member(request, db)
    if member.club_id != post.discussion.book.club_id:
        raise HTTPException(status_code=403, detail="Not a member of this club")
    
    # Validate content
    if not content or content.strip() == "":
        raise HTTPException(status_code=400, detail="Reply cannot be empty")
    
    reply = DiscussionPostReply(
        post_id=post_id,
        member_id=member.id,
        content=content.strip(),
        is_spoiler=is_spoiler
    )
    db.add(reply)
    db.commit()
    
    return RedirectResponse(
        url=f"/discussions/{post.discussion_id}",
        status_code=303
    )