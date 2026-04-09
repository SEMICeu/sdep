"""Add regulation to area.

Revision ID: 004
Revises: 003
Create Date: 2026-04-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Native PostgreSQL ENUM type for the regulation column.
# create_type=False here because we create/drop the type explicitly so we
# control ordering relative to add_column / drop_column.
regulation_enum = postgresql.ENUM(
    "listing",
    "activity",
    "all",
    name="regulation",
    create_type=False,
)


def upgrade() -> None:
    """Add regulation column to area table."""
    # Create the enum type first so the column can reference it.
    regulation_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "area",
        sa.Column(
            "regulation",
            regulation_enum,
            nullable=False,
            server_default=sa.text("'all'::regulation"),
        ),
    )
    # Remove server_default after backfill of existing rows
    op.alter_column("area", "regulation", server_default=None)


def downgrade() -> None:
    """Remove regulation column from area table."""
    op.drop_column("area", "regulation")
    regulation_enum.drop(op.get_bind(), checkfirst=True)
