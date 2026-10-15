# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Let people ask to join a public club, pending an admin's approval

Revision ID: 007
Revises: 006
Create Date: 2026-10-15

Listing a club publicly used to make it discoverable but not joinable: the
directory could only say "ask the organiser for a code". A join request is the
missing step. Rows live only while pending — approval creates the Member,
declining deletes the request.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'join_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('club_id', sa.Integer(), sa.ForeignKey('clubs.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('club_id', 'user_id', name='uq_join_request_club_user'),
    )
    op.create_index('ix_join_requests_id', 'join_requests', ['id'])
    op.create_index('ix_join_requests_club_id', 'join_requests', ['club_id'])
    op.create_index('ix_join_requests_user_id', 'join_requests', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_join_requests_user_id', table_name='join_requests')
    op.drop_index('ix_join_requests_club_id', table_name='join_requests')
    op.drop_index('ix_join_requests_id', table_name='join_requests')
    op.drop_table('join_requests')
