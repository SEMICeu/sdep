"""Add the listing table (random checks).

Revision ID: 008
Revises: 007
Create Date: 2026-09-16

One versioned table for the whole listing lifecycle (pending, clear, flagged,
acknowledged), see docs/LISTING_FUNC.md. The downgrade drops the table and its enum,
so listing data is lost on downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

listing_status_enum = postgresql.ENUM(
    "pending",
    "clear",
    "flagged",
    "acknowledged",
    name="listingstatus",
    create_type=False,
)


def upgrade() -> None:
    listing_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "listing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.String(length=64), nullable=False),
        sa.Column("listing_name", sa.String(length=64), nullable=True),
        sa.Column("status", listing_status_enum, nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("area_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("address_thoroughfare", sa.String(length=80), nullable=False),
        sa.Column("address_locator_designator_number", sa.Integer(), nullable=True),
        sa.Column("address_locator_designator_letter", sa.String(length=10), nullable=True),
        sa.Column("address_locator_designator_addition", sa.String(length=128), nullable=True),
        sa.Column("address_post_code", sa.String(length=10), nullable=False),
        sa.Column("address_post_name", sa.String(length=80), nullable=False),
        sa.Column("address_full_address", sa.String(length=328), nullable=False),
        sa.Column("declared_as_short_term_rental", sa.Boolean(), nullable=False),
        sa.Column("registration_number", sa.String(length=32), nullable=True),
        sa.Column("flags", postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("screened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["area_id"], ["area.id"], name=op.f("fk_listing_area_id_area")),
        sa.ForeignKeyConstraint(["platform_id"], ["platform.id"], name=op.f("fk_listing_platform_id_platform")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing")),
        sa.UniqueConstraint("listing_id", "platform_id", "created_at", name=op.f("uq_listing_listing_id_platform_id_created_at")),
    )
    op.create_index(op.f("ix_listing_listing_id"), "listing", ["listing_id"], unique=False)
    op.create_index(op.f("ix_listing_area_id"), "listing", ["area_id"], unique=False)
    op.create_index(op.f("ix_listing_platform_id"), "listing", ["platform_id"], unique=False)

    op.create_check_constraint(
        op.f("ck_listing_address_locator_designator_letter_alpha"),
        "listing",
        "address_locator_designator_letter IS NULL OR address_locator_designator_letter ~ '^[A-Za-z]+$'",
    )
    op.create_check_constraint(
        op.f("ck_listing_listing_id_format"),
        "listing",
        "listing_id ~ '^[A-Za-z0-9-]+$'",
    )
    op.create_check_constraint(
        op.f("ck_listing_status_flags"),
        "listing",
        "(status IN ('flagged', 'acknowledged') AND coalesce(array_length(flags, 1), 0) >= 1) "
        "OR (status IN ('pending', 'clear') AND coalesce(array_length(flags, 1), 0) = 0)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_listing_status_flags"), "listing", type_="check")
    op.drop_constraint(op.f("ck_listing_listing_id_format"), "listing", type_="check")
    op.drop_constraint(
        op.f("ck_listing_address_locator_designator_letter_alpha"),
        "listing",
        type_="check",
    )
    op.drop_index(op.f("ix_listing_platform_id"), table_name="listing")
    op.drop_index(op.f("ix_listing_area_id"), table_name="listing")
    op.drop_index(op.f("ix_listing_listing_id"), table_name="listing")
    op.drop_table("listing")

    listing_status_enum.drop(op.get_bind(), checkfirst=True)
