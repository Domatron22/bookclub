"""Add user profile fields and club visibility

Revision ID: 003
Revises: 002
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('bio', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('favorite_genre', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('favorite_book', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('favorite_author', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('bio_public', sa.Boolean(), nullable=True, server_default='1'))
        batch_op.add_column(sa.Column('favorites_public', sa.Boolean(), nullable=True, server_default='1'))
        batch_op.add_column(sa.Column('reading_history_public', sa.Boolean(), nullable=True, server_default='1'))

    with op.batch_alter_table('members') as batch_op:
        batch_op.add_column(sa.Column('profile_visible', sa.Boolean(), nullable=True, server_default='1'))


def downgrade() -> None:
    with op.batch_alter_table('members') as batch_op:
        batch_op.drop_column('profile_visible')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('reading_history_public')
        batch_op.drop_column('favorites_public')
        batch_op.drop_column('bio_public')
        batch_op.drop_column('favorite_author')
        batch_op.drop_column('favorite_book')
        batch_op.drop_column('favorite_genre')
        batch_op.drop_column('bio')
