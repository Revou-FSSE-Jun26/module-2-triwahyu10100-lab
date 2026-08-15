"""add role column to users

Revision ID: 513c63c14bff
Revises: 69cd99b04162
Create Date: 2026-08-15 12:12:33.342939

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '513c63c14bff'
down_revision = '69cd99b04162'
branch_labels = None
depends_on = None


def upgrade():
    # NOTE: auto-generated diff also included cosmetic index/constraint
    # differences unrelated to this change (see baseline migration for the
    # same reasoning) — trimmed by hand to just the role column addition.
    # server_default='customer' means existing rows are backfilled with a
    # concrete value instead of being left NULL.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), server_default='customer', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')
