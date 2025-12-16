"""Add customer_abbr column to customer table.

Revision ID: 3b0bf1328e70
Revises: 90af1e26ea70
Create Date: 2025-12-16 09:27:31.237160

"""

from typing import Sequence, Union

import sqlalchemy as sa, inspect

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "3b0bf1328e70"
down_revision: str = "90af1e26ea70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    engine = op.get_bind()
    inspector = inspect(engine)
    columns = [x["name"] for x in inspector.get_columns("customer")]

    if "customer_abbr" not in columns:
        op.add_column(
            "customer",
            sa.Column(
                "customer_abbr", sa.VARCHAR(), autoincrement=False, nullable=True
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""

    engine = op.get_bind()
    inspector = inspect(engine)
    columns = [x["name"] for x in inspector.get_columns("customer")]

    if "customer_abbr" in columns:
        op.drop_column("customer", "customer_abbr")
