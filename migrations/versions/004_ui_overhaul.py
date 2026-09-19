# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Club feature flags, book metadata, per-member reading progress, feedback

Revision ID: 004
Revises: 003
Create Date: 2026-08-26

Adds the server-side state the redesigned UI needs:

* club-level feature toggles and public-directory opt-in
* book page count and persisted placeholder-cover colours
* a per-member reading position for the current book
* a feedback table, mirrored to a GitHub issue when a token is configured

Existing selection settings (`book_selection_method`, `veto_percentage`,
`voting_percentage`) already cover the design's selection/veto/voting
thresholds and are deliberately left alone.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('clubs') as batch_op:
        # Off by default: hidden tallies are the design's stated preference,
        # and a migration must not publish anyone's club without asking.
        batch_op.add_column(sa.Column('votes_visible', sa.Boolean(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('is_public', sa.Boolean(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('feature_progress', sa.Boolean(), nullable=True, server_default='1'))
        batch_op.add_column(sa.Column('feature_recap', sa.Boolean(), nullable=True, server_default='1'))

    with op.batch_alter_table('books') as batch_op:
        batch_op.add_column(sa.Column('page_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cover_bg', sa.String(7), nullable=True))
        batch_op.add_column(sa.Column('cover_fg', sa.String(7), nullable=True))
        batch_op.add_column(sa.Column('open_library_id', sa.String(40), nullable=True))

    op.create_table(
        'member_book_progress',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('member_id', 'book_id', name='uq_member_book_progress'),
    )

    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('kind', sa.String(20), nullable=False, server_default='idea'),
        sa.Column('summary', sa.String(300), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('include_context', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('screen_label', sa.String(100), nullable=True),
        sa.Column('user_agent', sa.String(400), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('github_issue_number', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('feedback')
    op.drop_table('member_book_progress')

    with op.batch_alter_table('books') as batch_op:
        batch_op.drop_column('open_library_id')
        batch_op.drop_column('cover_fg')
        batch_op.drop_column('cover_bg')
        batch_op.drop_column('page_count')

    with op.batch_alter_table('clubs') as batch_op:
        batch_op.drop_column('feature_recap')
        batch_op.drop_column('feature_progress')
        batch_op.drop_column('is_public')
        batch_op.drop_column('votes_visible')
