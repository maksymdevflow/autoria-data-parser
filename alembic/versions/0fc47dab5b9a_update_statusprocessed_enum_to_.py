"""update_statusprocessed_enum_to_completed_failed

Revision ID: 0fc47dab5b9a
Revises: c6a0bf5270c8
Create Date: 2026-01-14 11:21:28.585528

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0fc47dab5b9a"
down_revision: Union[str, Sequence[str], None] = "c6a0bf5270c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Нічого не робимо — залишаємо старий enum statusprocessed як є
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Нічого не робимо
    pass
