from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
from .database import Base


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
    display_name = Column(String(100), nullable=False)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)  # Club admin status
    
    # Relationships
    club = relationship("Club", back_populates="members")
    book_suggestions = relationship("Book", back_populates="suggested_by_member")
    discussion_posts = relationship("DiscussionPost", back_populates="author")
    votes = relationship("Vote", back_populates="member")


class Book(Base):
    __tablename__ = "books"
    
    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    title = Column(String(300), nullable=False)
    author = Column(String(200), nullable=False)
    description = Column(Text)
    cover_url = Column(String(500))
    isbn = Column(String(13))
    
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
    author = relationship("Member")
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
    member = relationship("Member")


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
    member = relationship("Member")
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
    member = relationship("Member")


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
    member = relationship("Member")
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
    current_host_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    
    # Recurrence pattern - stored as simple strings for flexibility
    # Examples: "weekly", "biweekly", "monthly_day", "monthly_date"
    recurrence_pattern = Column(String(50), nullable=False)
    # Details: e.g., "Tuesday" for weekly, "4th Tuesday" for monthly_day, "15" for monthly_date
    recurrence_details = Column(String(100), nullable=False)
    
    default_duration_minutes = Column(Integer, default=120)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    club = relationship("Club", back_populates="meeting_schedule")
    current_host = relationship("Member", foreign_keys=[current_host_id])


class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True)
    host_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    
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
    host = relationship("Member")
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
    member = relationship("Member")


class BookVote(Base):
    __tablename__ = "book_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    vote_type = Column(String(20), default="upvote")  # upvote or veto
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    book = relationship("Book", back_populates="votes")
    member = relationship("Member")


class ReviewCommentLike(Base):
    __tablename__ = "review_comment_likes"
    
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("review_comments.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    comment = relationship("ReviewComment", back_populates="likes")
    member = relationship("Member")


class DiscussionPostLike(Base):
    __tablename__ = "discussion_post_likes"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("discussion_posts.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    post = relationship("DiscussionPost", back_populates="likes")
    member = relationship("Member")


class BookReader(Base):
    __tablename__ = "book_readers"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    book = relationship("Book", back_populates="readers")
    member = relationship("Member")