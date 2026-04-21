"""Add required address_full_address column.

Adds activity.address_full_address (String(318), NOT NULL) and backfills
existing rows by concatenating the component fields.

Revision ID: 006
Revises: 005
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add address_full_address, backfill from components, enforce NOT NULL."""
    # Step 1: add as nullable so existing rows don't violate the constraint
    op.add_column(
        "activity",
        sa.Column("address_full_address", sa.String(length=318), nullable=True),
    )

    # Step 2: backfill by concatenating the component fields
    # Pattern: "<thoroughfare> [<number>][<letter>][-<addition>], <post_code> <post_name>"
    # COALESCE handles the optional pieces (number, letter, addition) so NULL
    # propagation through `||` doesn't NULL-out the whole expression.
    op.execute(
        """
        UPDATE activity
        SET address_full_address = TRIM(
                address_thoroughfare
                || COALESCE(' ' || CAST(address_locator_designator_number AS VARCHAR), '')
                || COALESCE(address_locator_designator_letter, '')
                || COALESCE('-' || address_locator_designator_addition, '')
            )
            || ', '
            || address_post_code
            || ' '
            || address_post_name
        WHERE address_full_address IS NULL
        """
    )

    # Step 3: tighten to NOT NULL now that every row has a value
    op.alter_column(
        "activity",
        "address_full_address",
        existing_type=sa.String(length=318),
        nullable=False,
    )


def downgrade() -> None:
    """Drop address_full_address."""
    op.drop_column("activity", "address_full_address")
