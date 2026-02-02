"""add parse_status to links

Revision ID: a1b2c3d4e5f6
Revises: f2deeb9d38a7
Create Date: 2026-01-28 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2deeb9d38a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum для статусу парсингу лінка: pending (новий), parsed (вже спарсений). Lowercase для збігу з тим, що код відправляє в БД.
parse_status_enum = postgresql.ENUM("pending", "parsed", name="linkparsestatus")


def upgrade() -> None:
    bind = op.get_bind()
    parse_status_enum.create(bind, checkfirst=True)
    op.add_column(
        "links",
        sa.Column(
            "parse_status",
            parse_status_enum,
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade() -> None:
    op.drop_column("links", "parse_status")
    bind = op.get_bind()
    parse_status_enum.drop(bind, checkfirst=True)
