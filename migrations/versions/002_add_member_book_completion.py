"""Add member book completion tracking

Revision ID: 002
Revises: 001
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'member_book_completions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('member_id', 'book_id', name='uq_member_book_completion'),
    )
    op.create_index('ix_member_book_completions_member_id', 'member_book_completions', ['member_id'])
    op.create_index('ix_member_book_completions_book_id', 'member_book_completions', ['book_id'])


def downgrade() -> None:
    op.drop_index('ix_member_book_completions_book_id', table_name='member_book_completions')
    op.drop_index('ix_member_book_completions_member_id', table_name='member_book_completions')
    op.drop_table('member_book_completions')
