# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Let a member be deleted without taking their club's meetings with them

Revision ID: 006
Revises: 005
Create Date: 2026-09-19

Deleting an account used to fail outright. `User.members` cascades, but the
tables hanging off `members.id` were not reachable from the Member mapper, so
SQLAlchemy fell back to NULLing their non-nullable foreign keys:

    IntegrityError: NOT NULL constraint failed:
    member_book_completions.member_id

The fix is mostly in the models — every child collection now cascades — but
two of those references must *not* cascade. A meeting is the club's, not the
host's: losing a member should not delete meetings they happened to be
hosting, nor the club's recurring schedule. Those two columns become nullable
so the reference can simply be dropped, and the UI reads a hostless meeting as
"host to be decided".
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('meetings') as batch_op:
        batch_op.alter_column('host_id',
                              existing_type=sa.Integer(),
                              nullable=True)

    with op.batch_alter_table('meeting_schedules') as batch_op:
        batch_op.alter_column('current_host_id',
                              existing_type=sa.Integer(),
                              nullable=True)


def downgrade() -> None:
    # Narrowing back would fail on any row whose host has since left. Those
    # rows are exactly what this migration exists to allow, so re-point them
    # at a surviving member of the same club rather than dropping meetings the
    # club may still be planning around.
    conn = op.get_bind()

    conn.execute(sa.text("""
        UPDATE meetings
           SET host_id = (SELECT m.id FROM members m
                           WHERE m.club_id = meetings.club_id
                           ORDER BY m.is_admin DESC, m.joined_at
                           LIMIT 1)
         WHERE host_id IS NULL
    """))
    conn.execute(sa.text("""
        UPDATE meeting_schedules
           SET current_host_id = (SELECT m.id FROM members m
                                   WHERE m.club_id = meeting_schedules.club_id
                                   ORDER BY m.is_admin DESC, m.joined_at
                                   LIMIT 1)
         WHERE current_host_id IS NULL
    """))

    # A club with no members at all leaves nothing to point at; such rows
    # cannot satisfy a NOT NULL host and are removed.
    conn.execute(sa.text("DELETE FROM meetings WHERE host_id IS NULL"))
    conn.execute(sa.text("DELETE FROM meeting_schedules WHERE current_host_id IS NULL"))

    with op.batch_alter_table('meeting_schedules') as batch_op:
        batch_op.alter_column('current_host_id',
                              existing_type=sa.Integer(),
                              nullable=False)

    with op.batch_alter_table('meetings') as batch_op:
        batch_op.alter_column('host_id',
                              existing_type=sa.Integer(),
                              nullable=False)
