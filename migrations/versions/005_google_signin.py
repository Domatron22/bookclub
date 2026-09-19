# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Google sign-in identity columns

Revision ID: 005
Revises: 004
Create Date: 2026-08-26

Adds OpenID Connect identity to `users` so an account can be reached through
Google as well as (or instead of) a username and account secret.

`google_sub` is Google's stable subject identifier and carries the unique
constraint. Email is stored for display and support, but is deliberately *not*
the join key: Google users can change their address, and addresses can be
recycled — matching on email would let a new owner of an old address inherit
someone else's clubs.

`account_secret` becomes nullable, because accounts created through Google
never generate one. Anything that reads it must tolerate NULL.
"""
import secrets

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('google_sub', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(320), nullable=True))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('avatar_url', sa.String(500), nullable=True))
        # Unique so one Google identity can never be attached to two accounts;
        # NULLs are exempt in SQLite and PostgreSQL, so secret-only accounts
        # coexist freely.
        batch_op.create_index('ix_users_google_sub', ['google_sub'], unique=True)
        # Existing rows all have a secret, so widening to NULL loses nothing.
        batch_op.alter_column('account_secret',
                              existing_type=sa.String(64),
                              nullable=True)


def downgrade() -> None:
    # Accounts that only ever signed in with Google have no account_secret, so
    # narrowing the column back would fail on them. Give them one rather than
    # dropping the rows — the owner can recover it through support, and losing
    # a club membership to a downgrade would be worse.
    # Generated in Python rather than SQL so this works on PostgreSQL too —
    # `randomblob` and `gen_random_uuid` are not portable between them.
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id FROM users WHERE account_secret IS NULL"
    )).fetchall()
    for (user_id,) in rows:
        conn.execute(
            sa.text("UPDATE users SET account_secret = :s WHERE id = :i"),
            {"s": secrets.token_urlsafe(36), "i": user_id},
        )

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('account_secret',
                              existing_type=sa.String(64),
                              nullable=False)
        batch_op.drop_index('ix_users_google_sub')
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('email')
        batch_op.drop_column('google_sub')
