"""Add user authentication system

Revision ID: 001
Revises:
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
import secrets

# revision identifiers, used by Alembic.
revision = '001'
down_revision = '000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('username', sa.String(30), unique=True, nullable=False, index=True),
        sa.Column('account_secret', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    )

    # 2. Add nullable user_id to members
    with op.batch_alter_table('members') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_members_user_id', 'users', ['user_id'], ['id'])

    # 3. Backfill: create a User per unique session_id, link members
    bind = op.get_bind()

    # Use text() for raw SQL to work across SQLAlchemy versions
    members_rows = bind.execute(sa.text(
        "SELECT id, session_id, display_name FROM members ORDER BY id"
    )).fetchall()

    # Group members by session_id (one User per unique session_id)
    seen_sessions = {}  # session_id -> user_id
    for row in members_rows:
        member_id, session_id, display_name = row[0], row[1], row[2]
        if session_id not in seen_sessions:
            # Create a new User for this session_id
            username = f"user_{member_id}"
            account_secret = secrets.token_urlsafe(36)
            now = datetime.utcnow()

            bind.execute(sa.text(
                "INSERT INTO users (username, account_secret, display_name, created_at, last_seen_at) "
                "VALUES (:username, :secret, :display_name, :created_at, :last_seen_at)"
            ), {
                "username": username,
                "secret": account_secret,
                "display_name": display_name,
                "created_at": now,
                "last_seen_at": now,
            })

            # Get the id of the newly inserted user
            user_id = bind.execute(sa.text("SELECT last_insert_rowid()")).scalar()
            seen_sessions[session_id] = user_id

        # Link this member to the user
        bind.execute(sa.text(
            "UPDATE members SET user_id = :user_id WHERE id = :member_id"
        ), {"user_id": seen_sessions[session_id], "member_id": member_id})

    # 4. Make user_id NOT NULL and drop session_id
    with op.batch_alter_table('members') as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.drop_column('session_id')


def downgrade() -> None:
    # Re-add session_id as nullable (cannot recover original tokens)
    with op.batch_alter_table('members') as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.String(64), nullable=True))
        batch_op.drop_column('user_id')

    op.drop_table('users')
