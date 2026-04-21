"""Require number_of_guests and country_of_guests; enforce cardinality.

Backfills existing rows so that both columns are non-null and the number of
guests equals the length of country_of_guests, then makes both columns NOT NULL
and swaps the CHECK constraints to drop the IS NULL branch and add a cardinality
CHECK (PostgreSQL only).

Revision ID: 007
Revises: 006
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill guest columns, enforce NOT NULL, swap CHECK constraints."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ── Step 1: backfill NULL and mismatched rows ───────────────────────
    if is_postgres:
        # Both NULL → default to a single anonymous guest
        op.execute(
            """
            UPDATE activity
            SET number_of_guests = 1,
                country_of_guests = ARRAY['N/A']
            WHERE number_of_guests IS NULL
              AND country_of_guests IS NULL
            """
        )
        # number_of_guests NULL, country_of_guests set → derive number from array
        op.execute(
            """
            UPDATE activity
            SET number_of_guests = array_length(country_of_guests, 1)
            WHERE number_of_guests IS NULL
              AND country_of_guests IS NOT NULL
            """
        )
        # country_of_guests NULL, number_of_guests set → pad with 'N/A'
        op.execute(
            """
            UPDATE activity
            SET country_of_guests = array_fill('N/A'::varchar, ARRAY[number_of_guests])
            WHERE country_of_guests IS NULL
              AND number_of_guests IS NOT NULL
            """
        )
        # Both set but lengths differ → truncate or pad with 'N/A'
        op.execute(
            """
            UPDATE activity
            SET country_of_guests = (
                country_of_guests[1:number_of_guests]
                || array_fill(
                    'N/A'::varchar,
                    ARRAY[GREATEST(number_of_guests - array_length(country_of_guests, 1), 0)]
                )
            )
            WHERE number_of_guests <> array_length(country_of_guests, 1)
            """
        )

    # ── Step 2: make both columns NOT NULL ──────────────────────────────
    op.alter_column("activity", "number_of_guests", existing_type=sa.Integer(), nullable=False)
    # country_of_guests uses the StringArray column type (ARRAY(String) on PG, JSON-encoded on SQLite)
    op.alter_column("activity", "country_of_guests", nullable=False)

    # ── Step 3: swap CHECK constraints ──────────────────────────────────
    op.drop_constraint("ck_activity_number_of_guests_range", "activity", type_="check")
    op.create_check_constraint(
        "ck_activity_number_of_guests_range",
        "activity",
        "number_of_guests >= 1 AND number_of_guests <= 1024",
    )

    if is_postgres:
        op.drop_constraint("ck_activity_country_of_guests_length", "activity", type_="check")
        op.create_check_constraint(
            "ck_activity_country_of_guests_length",
            "activity",
            "array_length(country_of_guests, 1) >= 1 AND array_length(country_of_guests, 1) <= 1024",
        )
        op.create_check_constraint(
            "ck_activity_guests_cardinality",
            "activity",
            "number_of_guests = array_length(country_of_guests, 1)",
        )


def downgrade() -> None:
    """Reverse: drop cardinality CHECK, restore IS NULL-tolerant CHECKs, allow NULL."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.drop_constraint("ck_activity_guests_cardinality", "activity", type_="check")
        op.drop_constraint("ck_activity_country_of_guests_length", "activity", type_="check")
        op.create_check_constraint(
            "ck_activity_country_of_guests_length",
            "activity",
            "country_of_guests IS NULL OR (array_length(country_of_guests, 1) >= 1 AND array_length(country_of_guests, 1) <= 1024)",
        )

    op.drop_constraint("ck_activity_number_of_guests_range", "activity", type_="check")
    op.create_check_constraint(
        "ck_activity_number_of_guests_range",
        "activity",
        "number_of_guests IS NULL OR (number_of_guests >= 1 AND number_of_guests <= 1024)",
    )

    op.alter_column("activity", "country_of_guests", nullable=True)
    op.alter_column("activity", "number_of_guests", existing_type=sa.Integer(), nullable=True)
