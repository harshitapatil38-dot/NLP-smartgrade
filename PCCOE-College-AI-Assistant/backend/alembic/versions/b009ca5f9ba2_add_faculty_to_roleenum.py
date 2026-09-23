"""Add FACULTY to RoleEnum

Revision ID: b009ca5f9ba2
Revises: 21b30b9f4f92
Create Date: 2026-09-21 10:39:38.209750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b009ca5f9ba2'
down_revision: Union[str, Sequence[str], None] = '21b30b9f4f92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("COMMIT")
    op.execute("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'FACULTY'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
