# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_current_user, require_member_for_club
from ..models import Discussion, DiscussionPost, DiscussionPostLike, DiscussionComment, DiscussionCommentLike, Book
from ..templating import templates, base_context

router = APIRouter()


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

    # Members only: a club's reading, and the conversation around it, is
    # private to the people in it.
    user = require_current_user(request, db)
    current_member = require_member_for_club(user, book.club_id, db)

    return templates.TemplateResponse(
        request,
        "discussions/list.html",
        {
            **base_context(request, db, user, club=book.club),
            "title": f"Discussions - {book.title}",
            "book": book,
            "club": book.club,
            "current_member": current_member,
            "discussions": book.discussions,
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

    user = require_current_user(request, db)
    require_member_for_club(user, book.club_id, db)

    discussion = Discussion(book_id=book_id, title=title)
    db.add(discussion)
    db.commit()

    return RedirectResponse(url=f"/discussions/{discussion.id}", status_code=303)


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

    user = require_current_user(request, db)
    current_member = require_member_for_club(user, discussion.book.club_id, db)

    return templates.TemplateResponse(
        request,
        "discussions/view.html",
        {
            **base_context(request, db, user, club=discussion.book.club),
            "title": discussion.title,
            "discussion": discussion,
            "book": discussion.book,
            "club": discussion.book.club,
            "current_member": current_member,
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

    user = require_current_user(request, db)
    member = require_member_for_club(user, discussion.book.club_id, db)

    post = DiscussionPost(
        discussion_id=discussion_id,
        author_id=member.id,
        content=content,
        is_spoiler=is_spoiler
    )
    db.add(post)
    db.commit()

    return RedirectResponse(url=f"/discussions/{discussion_id}", status_code=303)


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

    user = require_current_user(request, db)
    member = require_member_for_club(user, post.discussion.book.club_id, db)

    existing_like = db.query(DiscussionPostLike).filter(
        DiscussionPostLike.post_id == post_id,
        DiscussionPostLike.member_id == member.id
    ).first()

    if existing_like:
        db.delete(existing_like)
    else:
        like = DiscussionPostLike(post_id=post_id, member_id=member.id)
        db.add(like)

    db.commit()

    return RedirectResponse(url=f"/discussions/{post.discussion_id}", status_code=303)


@router.post("/post/{post_id}/comment")
async def add_comment(
    request: Request,
    post_id: int,
    content: str = Form(...),
    is_spoiler: bool = Form(False),
    parent_comment_id: int = Form(None),
    db: Session = Depends(get_db)
):
    """Add a comment to a discussion post (or reply to another comment)"""
    post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, post.discussion.book.club_id, db)

    if not content or content.strip() == "":
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    comment = DiscussionComment(
        post_id=post_id,
        parent_comment_id=parent_comment_id,
        author_id=member.id,
        content=content.strip(),
        is_spoiler=is_spoiler
    )
    db.add(comment)
    db.commit()

    return RedirectResponse(url=f"/discussions/{post.discussion_id}", status_code=303)


@router.post("/comment/{comment_id}/like")
async def like_comment(
    request: Request,
    comment_id: int,
    db: Session = Depends(get_db)
):
    """Like or unlike a comment"""
    comment = db.query(DiscussionComment).filter(DiscussionComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user = require_current_user(request, db)
    member = require_member_for_club(user, comment.post.discussion.book.club_id, db)

    existing_like = db.query(DiscussionCommentLike).filter(
        DiscussionCommentLike.comment_id == comment_id,
        DiscussionCommentLike.member_id == member.id
    ).first()

    if existing_like:
        db.delete(existing_like)
    else:
        like = DiscussionCommentLike(comment_id=comment_id, member_id=member.id)
        db.add(like)

    db.commit()

    return RedirectResponse(url=f"/discussions/{comment.post.discussion_id}", status_code=303)
