# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(30), unique=True, nullable=False, index=True)
    # Nullable: accounts created through Google sign-in never get a secret
    # unless the owner asks for one.
    account_secret = Column(String(64), nullable=True)

    # Google sign-in. `google_sub` is Google's stable subject identifier and is
    # the join key — email is *not*, because people change their Google address
    # and a recycled address must never inherit someone else's clubs.
    google_sub = Column(String(64), unique=True, nullable=True, index=True)
    email = Column(String(320), nullable=True)
    email_verified = Column(Boolean, default=False)
    avatar_url = Column(String(500), nullable=True)
    display_name = Column(String(100), nullable=True)  # optional account-level fallback
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    # Profile fields
    bio = Column(Text, nullable=True)
    favorite_genre = Column(String(100), nullable=True)
    favorite_book = Column(String(200), nullable=True)
    favorite_author = Column(String(100), nullable=True)

    # Privacy toggles (default public)
    bio_public = Column(Boolean, default=True)
    favorites_public = Column(Boolean, default=True)
    reading_history_public = Column(Boolean, default=True)

    # Relationships
    members = relationship("Member", back_populates="user", cascade="all, delete-orphan")


class Club(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(8), unique=True, nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Admin Settings
    veto_enabled = Column(Boolean, default=True)
    veto_percentage = Column(Integer, default=50)  # Percentage of members needed to veto
    book_selection_method = Column(String(20), default="random")  # random or voting
    voting_percentage = Column(Integer, default=50)  # Percentage needed to select via voting
    votes_visible = Column(Boolean, default=False)  # Show running tallies before voting closes

    # Discoverability + per-club feature toggles
    is_public = Column(Boolean, default=False)  # List in the public directory
    feature_progress = Column(Boolean, default=True)  # Per-member reading progress
    feature_recap = Column(Boolean, default=True)  # Year-in-books recap

    # Relationships
    books = relationship("Book", back_populates="club", cascade="all, delete-orphan")
    members = relationship("Member", back_populates="club", cascade="all, delete-orphan")
    meeting_schedule = relationship("MeetingSchedule", back_populates="club", uselist=False, cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="club", cascade="all, delete-orphan")

    @staticmethod
    def generate_code():
        """Generate a unique 8-character club code"""
        return secrets.token_urlsafe(6)[:8].upper()


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable during migration
    display_name = Column(String(100), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)  # Club admin status
    profile_visible = Column(Boolean, default=True)  # Show this club on member's profile

    # Relationships
    #
    # Every table that references members.id is reachable from here with
    # `delete-orphan`, so removing a Member takes its rows with it. Without
    # these, SQLAlchemy tries to NULL out non-nullable FKs and the delete
    # fails outright — which is what used to make account deletion a 500.
    #
    # The exception is `book_suggestions`: Book.suggested_by is nullable on
    # purpose, so a departing member's suggestions stay on the shortlist and
    # simply lose their attribution.
    club = relationship("Club", back_populates="members")
    user = relationship("User", back_populates="members")
    book_suggestions = relationship("Book", back_populates="suggested_by_member")

    discussion_posts = relationship(
        "DiscussionPost", back_populates="author", cascade="all, delete-orphan")
    discussion_comments = relationship(
        "DiscussionComment", back_populates="author", cascade="all, delete-orphan")
    discussion_post_likes = relationship(
        "DiscussionPostLike", back_populates="member", cascade="all, delete-orphan")
    discussion_comment_likes = relationship(
        "DiscussionCommentLike", back_populates="member", cascade="all, delete-orphan")
    ratings = relationship(
        "Rating", back_populates="member", cascade="all, delete-orphan")
    review_likes = relationship(
        "ReviewLike", back_populates="member", cascade="all, delete-orphan")
    review_comments = relationship(
        "ReviewComment", back_populates="member", cascade="all, delete-orphan")
    review_comment_likes = relationship(
        "ReviewCommentLike", back_populates="member", cascade="all, delete-orphan")
    votes = relationship(
        "Vote", back_populates="member", cascade="all, delete-orphan")
    book_votes = relationship(
        "BookVote", back_populates="member", cascade="all, delete-orphan")
    book_completions = relationship(
        "MemberBookCompletion", back_populates="member", cascade="all, delete-orphan")
    book_progress = relationship(
        "MemberBookProgress", back_populates="member", cascade="all, delete-orphan")
    book_readings = relationship(
        "BookReader", back_populates="member", cascade="all, delete-orphan")
    meeting_rsvps = relationship(
        "MeetingRSVP", back_populates="member", cascade="all, delete-orphan")

    # Hosting is *not* a cascade: a club losing a member must not lose the
    # meetings they happened to be hosting. These nullify instead, and the
    # templates read a hostless meeting as "host to be decided".
    hosted_meetings = relationship("Meeting", back_populates="host")
    hosted_schedules = relationship(
        "MeetingSchedule", back_populates="current_host",
        foreign_keys="MeetingSchedule.current_host_id")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    title = Column(String(300), nullable=False)
    author = Column(String(200), nullable=False)
    description = Column(Text)
    cover_url = Column(String(500))
    isbn = Column(String(13))
    page_count = Column(Integer)  # Denominator for "Page n of N"

    # Placeholder-cover colours, persisted so a cover never changes shade.
    # Null falls back to a deterministic pick keyed on title + author.
    cover_bg = Column(String(7))
    cover_fg = Column(String(7))
    open_library_id = Column(String(40))

    # Suggestion tracking
    suggested_by = Column(Integer, ForeignKey("members.id"))
    suggested_at = Column(DateTime, default=datetime.utcnow)

    # Selection tracking
    status = Column(String(20), default="suggested")  # suggested, selected, reading, completed
    selected_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Weighting for random selection
    weight = Column(Float, default=1.0)
    vetoed = Column(Boolean, default=False)

    # Relationships
    club = relationship("Club", back_populates="books")
    suggested_by_member = relationship("Member", back_populates="book_suggestions")
    discussions = relationship("Discussion", back_populates="book", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="book", cascade="all, delete-orphan")
    votes = relationship("BookVote", back_populates="book", cascade="all, delete-orphan")
    readers = relationship("BookReader", back_populates="book", cascade="all, delete-orphan")
    completions = relationship("MemberBookCompletion", back_populates="book", cascade="all, delete-orphan")
    progress_entries = relationship("MemberBookProgress", back_populates="book", cascade="all, delete-orphan")


class MemberBookCompletion(Base):
    __tablename__ = "member_book_completions"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("member_id", "book_id", name="uq_member_book_completion"),
    )

    # Relationships
    member = relationship("Member", back_populates="book_completions")
    book = relationship("Book", back_populates="completions")


class MemberBookProgress(Base):
    """How far a member has read into a given book, as a page number."""
    __tablename__ = "member_book_progress"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    page = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("member_id", "book_id", name="uq_member_book_progress"),
    )

    member = relationship("Member", back_populates="book_progress")
    book = relationship("Book", back_populates="progress_entries")


class Feedback(Base):
    """A submitted piece of feedback, mirrored to a GitHub issue when possible."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    kind = Column(String(20), default="idea")  # idea | bug | confusing | praise
    summary = Column(String(300), nullable=False)
    details = Column(Text)
    include_context = Column(Boolean, default=True)

    # Only populated when include_context was checked.
    screen_label = Column(String(100))
    user_agent = Column(String(400))

    created_at = Column(DateTime, default=datetime.utcnow)
    github_issue_number = Column(Integer)  # Null when issue creation failed or is unconfigured

    user = relationship("User")


class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    title = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="discussions")
    posts = relationship("DiscussionPost", back_populates="discussion", cascade="all, delete-orphan")


class DiscussionPost(Base):
    __tablename__ = "discussion_posts"

    id = Column(Integer, primary_key=True, index=True)
    discussion_id = Column(Integer, ForeignKey("discussions.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_spoiler = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    discussion = relationship("Discussion", back_populates="posts")
    author = relationship("Member", back_populates="discussion_posts")
    likes = relationship("DiscussionPostLike", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("DiscussionComment", back_populates="post", cascade="all, delete-orphan", foreign_keys="DiscussionComment.post_id")


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("discussion_posts.id"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("discussion_comments.id"), nullable=True)  # Self-referencing for infinite nesting
    author_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_spoiler = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("DiscussionPost", back_populates="comments", foreign_keys=[post_id])
    author = relationship("Member", back_populates="discussion_comments")
    parent_comment = relationship("DiscussionComment", remote_side=[id], back_populates="child_comments")
    child_comments = relationship("DiscussionComment", back_populates="parent_comment", cascade="all, delete-orphan")
    likes = relationship("DiscussionCommentLike", back_populates="comment", cascade="all, delete-orphan")


class DiscussionCommentLike(Base):
    __tablename__ = "discussion_comment_likes"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("discussion_comments.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    comment = relationship("DiscussionComment", back_populates="likes")
    member = relationship("Member", back_populates="discussion_comment_likes")


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="ratings")
    member = relationship("Member", back_populates="ratings")
    likes = relationship("ReviewLike", back_populates="rating", cascade="all, delete-orphan")
    comments = relationship("ReviewComment", back_populates="rating", cascade="all, delete-orphan")


class ReviewLike(Base):
    __tablename__ = "review_likes"

    id = Column(Integer, primary_key=True, index=True)
    rating_id = Column(Integer, ForeignKey("ratings.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    rating = relationship("Rating", back_populates="likes")
    member = relationship("Member", back_populates="review_likes")


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, index=True)
    rating_id = Column(Integer, ForeignKey("ratings.id"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("review_comments.id"), nullable=True)  # Self-referencing for infinite nesting
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    rating = relationship("Rating", back_populates="comments", foreign_keys=[rating_id])
    member = relationship("Member", back_populates="review_comments")
    parent_comment = relationship("ReviewComment", remote_side=[id], back_populates="child_comments")
    child_comments = relationship("ReviewComment", back_populates="parent_comment", cascade="all, delete-orphan")
    likes = relationship("ReviewCommentLike", back_populates="comment", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    vote_type = Column(String(20))  # upvote, downvote, veto
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    member = relationship("Member", back_populates="votes")


class MeetingSchedule(Base):
    __tablename__ = "meeting_schedules"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False, unique=True)
    # Nullable: the host may leave the club. See Member.hosted_schedules.
    current_host_id = Column(Integer, ForeignKey("members.id"), nullable=True)

    # Recurrence pattern - stored as simple strings for flexibility
    recurrence_pattern = Column(String(50), nullable=False)
    recurrence_details = Column(String(100), nullable=False)

    default_duration_minutes = Column(Integer, default=120)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    club = relationship("Club", back_populates="meeting_schedule")
    current_host = relationship(
        "Member", back_populates="hosted_schedules", foreign_keys=[current_host_id])


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True)
    # Nullable: the host may leave the club. See Member.hosted_meetings.
    host_id = Column(Integer, ForeignKey("members.id"), nullable=True)

    title = Column(String(200), nullable=False)
    meeting_datetime = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=120)
    location = Column(String(500))  # Physical location or virtual link
    description = Column(Text)
    notes = Column(Text)  # Post-meeting notes

    status = Column(String(20), default="scheduled")  # scheduled, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    club = relationship("Club", back_populates="meetings")
    book = relationship("Book")
    host = relationship("Member", back_populates="hosted_meetings")
    rsvps = relationship("MeetingRSVP", back_populates="meeting", cascade="all, delete-orphan")


class MeetingRSVP(Base):
    __tablename__ = "meeting_rsvps"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)

    status = Column(String(20), default="yes")  # yes, no, maybe
    bringing = Column(Text)  # What they're bringing (food, drinks, etc.)
    notes = Column(Text)  # Additional notes

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    meeting = relationship("Meeting", back_populates="rsvps")
    member = relationship("Member", back_populates="meeting_rsvps")


class BookVote(Base):
    __tablename__ = "book_votes"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    vote_type = Column(String(20), default="upvote")  # upvote or veto
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="votes")
    member = relationship("Member", back_populates="book_votes")


class ReviewCommentLike(Base):
    __tablename__ = "review_comment_likes"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("review_comments.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    comment = relationship("ReviewComment", back_populates="likes")
    member = relationship("Member", back_populates="review_comment_likes")


class DiscussionPostLike(Base):
    __tablename__ = "discussion_post_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("discussion_posts.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("DiscussionPost", back_populates="likes")
    member = relationship("Member", back_populates="discussion_post_likes")


class BookReader(Base):
    __tablename__ = "book_readers"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="readers")
    member = relationship("Member", back_populates="book_readings")
