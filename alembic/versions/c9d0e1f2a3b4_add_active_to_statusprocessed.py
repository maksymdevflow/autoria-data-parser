"""Add 'ACTIVE' to statusprocessed enum

Revision ID: c9d0e1f2a3b4
Revises: a8b9c0d1e2f3
Create Date: 2026-01-31

"""

from typing import Sequence, Union

from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE statusprocessed ADD VALUE IF NOT EXISTS 'active'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values easily
    pass
