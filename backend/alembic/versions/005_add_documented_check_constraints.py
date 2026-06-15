"""Add documented DB-level CHECK constraints.

Revision ID: 005
Revises: 004
Create Date: 2026-05-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _assert_existing_rows_satisfy_constraints() -> None:
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            """
            SELECT
                (
                    SELECT count(*)
                    FROM activity
                    WHERE temporal_start_date_time >= temporal_end_date_time
                ) AS activity_temporal_order,
                (
                    SELECT count(*)
                    FROM activity
                    WHERE EXTRACT(YEAR FROM temporal_start_date_time) < 2025
                ) AS activity_temporal_start_year,
                (
                    SELECT count(*)
                    FROM activity
                    WHERE address_locator_designator_letter IS NOT NULL
                    AND address_locator_designator_letter !~ '^[A-Za-z]+$'
                ) AS activity_locator_designator_letter,
                (
                    SELECT count(*)
                    FROM activity
                    WHERE activity_id !~ '^[A-Za-z0-9-]+$'
                ) AS activity_id_format,
                (
                    SELECT count(*)
                    FROM area
                    WHERE area_id !~ '^[A-Za-z0-9-]+$'
                ) AS area_id_format
            """
        )
    ).one()

    violations = {
        key: value
        for key, value in row._mapping.items()
        if value
    }
    if violations:
        details = ", ".join(
            f"{constraint}: {count}" for constraint, count in violations.items()
        )
        raise RuntimeError(
            "Existing rows violate documented CHECK constraints: " + details
        )


def upgrade() -> None:
    _assert_existing_rows_satisfy_constraints()

    op.create_check_constraint(
        op.f("ck_activity_temporal_start_before_end"),
        "activity",
        "temporal_start_date_time < temporal_end_date_time",
    )
    op.create_check_constraint(
        op.f("ck_activity_temporal_start_year_ge_2025"),
        "activity",
        "EXTRACT(YEAR FROM temporal_start_date_time) >= 2025",
    )
    op.create_check_constraint(
        op.f("ck_activity_address_locator_designator_letter_alpha"),
        "activity",
        "address_locator_designator_letter IS NULL OR address_locator_designator_letter ~ '^[A-Za-z]+$'",
    )
    op.create_check_constraint(
        op.f("ck_activity_activity_id_format"),
        "activity",
        "activity_id ~ '^[A-Za-z0-9-]+$'",
    )
    op.create_check_constraint(
        op.f("ck_area_area_id_format"),
        "area",
        "area_id ~ '^[A-Za-z0-9-]+$'",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_area_area_id_format"),
        "area",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_activity_activity_id_format"),
        "activity",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_activity_address_locator_designator_letter_alpha"),
        "activity",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_activity_temporal_start_year_ge_2025"),
        "activity",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_activity_temporal_start_before_end"),
        "activity",
        type_="check",
    )
