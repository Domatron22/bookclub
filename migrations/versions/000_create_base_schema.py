"""Create base schema

Revision ID: 000
Revises:
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'clubs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(8), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('veto_enabled', sa.Boolean(), default=True),
        sa.Column('veto_percentage', sa.Integer(), default=50),
        sa.Column('book_selection_method', sa.String(20), default='random'),
        sa.Column('voting_percentage', sa.Integer(), default=50),
    )

    op.create_table(
        'members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('club_id', sa.Integer(), sa.ForeignKey('clubs.id'), nullable=False),
        sa.Column('session_id', sa.String(64), unique=True, nullable=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('joined_at', sa.DateTime()),
        sa.Column('is_admin', sa.Boolean(), default=False),
    )

    op.create_table(
        'books',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('club_id', sa.Integer(), sa.ForeignKey('clubs.id'), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('author', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('cover_url', sa.String(500)),
        sa.Column('isbn', sa.String(13)),
        sa.Column('suggested_by', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('suggested_at', sa.DateTime()),
        sa.Column('status', sa.String(20), default='suggested'),
        sa.Column('selected_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('weight', sa.Float(), default=1.0),
        sa.Column('vetoed', sa.Boolean(), default=False),
    )

    op.create_table(
        'discussions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'discussion_posts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('discussion_id', sa.Integer(), sa.ForeignKey('discussions.id'), nullable=False),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_spoiler', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'discussion_comments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('discussion_posts.id'), nullable=False),
        sa.Column('parent_comment_id', sa.Integer(), sa.ForeignKey('discussion_comments.id'), nullable=True),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_spoiler', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'discussion_comment_likes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('comment_id', sa.Integer(), sa.ForeignKey('discussion_comments.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'discussion_post_likes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('discussion_posts.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'ratings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('review', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table(
        'review_likes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rating_id', sa.Integer(), sa.ForeignKey('ratings.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'review_comments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rating_id', sa.Integer(), sa.ForeignKey('ratings.id'), nullable=False),
        sa.Column('parent_comment_id', sa.Integer(), sa.ForeignKey('review_comments.id'), nullable=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'review_comment_likes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('comment_id', sa.Integer(), sa.ForeignKey('review_comments.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'votes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('vote_type', sa.String(20)),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'book_votes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('vote_type', sa.String(20), default='upvote'),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'book_readers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime()),
    )

    op.create_table(
        'meeting_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('club_id', sa.Integer(), sa.ForeignKey('clubs.id'), nullable=False, unique=True),
        sa.Column('current_host_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('recurrence_pattern', sa.String(50), nullable=False),
        sa.Column('recurrence_details', sa.String(100), nullable=False),
        sa.Column('default_duration_minutes', sa.Integer(), default=120),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'meetings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('club_id', sa.Integer(), sa.ForeignKey('clubs.id'), nullable=False),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=True),
        sa.Column('host_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('meeting_datetime', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), default=120),
        sa.Column('location', sa.String(500)),
        sa.Column('description', sa.Text()),
        sa.Column('notes', sa.Text()),
        sa.Column('status', sa.String(20), default='scheduled'),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
    )

    op.create_table(
        'meeting_rsvps',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('meeting_id', sa.Integer(), sa.ForeignKey('meetings.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('status', sa.String(20), default='yes'),
        sa.Column('bringing', sa.Text()),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('meeting_rsvps')
    op.drop_table('meetings')
    op.drop_table('meeting_schedules')
    op.drop_table('book_readers')
    op.drop_table('book_votes')
    op.drop_table('votes')
    op.drop_table('review_comment_likes')
    op.drop_table('review_comments')
    op.drop_table('review_likes')
    op.drop_table('ratings')
    op.drop_table('discussion_post_likes')
    op.drop_table('discussion_comment_likes')
    op.drop_table('discussion_comments')
    op.drop_table('discussion_posts')
    op.drop_table('discussions')
    op.drop_table('books')
    op.drop_table('members')
    op.drop_table('clubs')
