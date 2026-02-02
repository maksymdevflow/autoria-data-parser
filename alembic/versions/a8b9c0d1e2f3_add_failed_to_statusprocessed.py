"""Add 'failed' to statusprocessed enum

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-01-31

"""

from typing import Sequence, Union

from alembic import op


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE statusprocessed ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values easily
    pass
