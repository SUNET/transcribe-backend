"""Add column for notification preferences.

Revision ID: 2f4030b1c1ec
Revises: 8503ec0ebe90
Create Date: 2026-01-05 19:44:27.489757

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "2f4030b1c1ec"
down_revision: Union[str, Sequence[str], None] = "8503ec0ebe90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    engine = op.get_bind()
    inspector = inspect(engine)
    columns = [x["name"] for x in inspector.get_columns("users")]

    if "notifications" not in columns:
        op.add_column(
            "users",
            sa.Column("notifications", sa.VARCHAR(), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    engine = op.get_bind()
    inspector = inspect(engine)
    columns = [x["name"] for x in inspector.get_columns("users")]

    if "notifications" in columns:
        op.drop_column("users", "notifications")
