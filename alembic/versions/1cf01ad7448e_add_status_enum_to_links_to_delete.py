"""add status enum to links_to_delete

Revision ID: 1cf01ad7448e
Revises: 1b17742843f3
Create Date: 2026-01-27 13:44:55.791664

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1cf01ad7448e"
down_revision: Union[str, Sequence[str], None] = "1b17742843f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


status_enum = postgresql.ENUM("process", "completed", name="statuslinkchange")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # Створюємо тип ENUM, якщо ще не існує
    status_enum.create(bind, checkfirst=True)

    # Додаємо колонку status до обох таблиць
    op.add_column(
        "links_to_create",
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="process",
        ),
    )
    op.add_column(
        "links_to_delete",
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="process",
        ),
    )

    # Прибираємо default, якщо він не потрібен на рівні схеми
    op.alter_column("links_to_create", "status", server_default=None)
    op.alter_column("links_to_delete", "status", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_column("links_to_delete", "status")
    op.drop_column("links_to_create", "status")

    # Дропаємо ENUM тип
    status_enum.drop(bind, checkfirst=True)
