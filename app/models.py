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
    
    # Relationships
    books = relationship("Book", back_populates="club", cascade="all, delete-orphan")
    members = relationship("Member", back_populates="club", cascade="all, delete-orphan")
    
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


class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    book = relationship("Book", back_populates="ratings")


class Vote(Base):
    __tablename__ = "votes"
    
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    vote_type = Column(String(20))  # upvote, downvote, veto
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    member = relationship("Member", back_populates="votes")
