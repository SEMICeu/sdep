"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2025-12-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create competent_authority table
    op.create_table(
        "competent_authority",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competent_authority_id", sa.String(length=64), nullable=False),
        sa.Column("competent_authority_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competent_authority")),
        sa.UniqueConstraint("competent_authority_id", "created_at", name=op.f("uq_competent_authority_competent_authority_id_created_at")),
    )
    op.create_index(op.f("ix_competent_authority_competent_authority_id"), "competent_authority", ["competent_authority_id"], unique=False)

    # Create area table
    op.create_table(
        "area",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=False),
        sa.Column("area_name", sa.String(length=64), nullable=True),
        sa.Column("competent_authority_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=64), nullable=False),
        sa.Column("filedata", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(filedata) <= 1048576", name="ck_area_filedata_max_size"),
        sa.ForeignKeyConstraint(["competent_authority_id"], ["competent_authority.id"], name=op.f("fk_area_competent_authority_id_competent_authority")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_area")),
        sa.UniqueConstraint("area_id", "competent_authority_id", "created_at", name=op.f("uq_area_area_id_competent_authority_id_created_at")),
    )
    op.create_index(op.f("ix_area_area_id"), "area", ["area_id"], unique=False)
    op.create_index(op.f("ix_area_competent_authority_id"), "area", ["competent_authority_id"], unique=False)

    # Create platform table
    op.create_table(
        "platform",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.String(length=64), nullable=False),
        sa.Column("platform_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform")),
        sa.UniqueConstraint("platform_id", "created_at", name=op.f("uq_platform_platform_id_created_at")),
    )
    op.create_index(op.f("ix_platform_platform_id"), "platform", ["platform_id"], unique=False)

    # Create activity table
    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("activity_name", sa.String(length=64), nullable=True),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("area_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=128), nullable=False),
        sa.Column("address_street", sa.String(length=64), nullable=False),
        sa.Column("address_number", sa.Integer(), nullable=False),
        sa.Column("address_letter", sa.String(length=1), nullable=True),
        sa.Column("address_addition", sa.String(length=10), nullable=True),
        sa.Column("address_postal_code", sa.String(length=8), nullable=False),
        sa.Column("address_city", sa.String(length=64), nullable=False),
        sa.Column("registration_number", sa.String(length=32), nullable=False),
        sa.Column("number_of_guests", sa.Integer(), nullable=True),
        sa.Column(
            "country_of_guests",
            postgresql.ARRAY(sa.String(length=32)),
            nullable=True,
        ),
        sa.Column("temporal_start_date_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temporal_end_date_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("number_of_guests IS NULL OR (number_of_guests >= 1 AND number_of_guests <= 1024)", name="ck_activity_number_of_guests_range"),
        sa.CheckConstraint("country_of_guests IS NULL OR (array_length(country_of_guests, 1) >= 1 AND array_length(country_of_guests, 1) <= 1024)", name="ck_activity_country_of_guests_length"),
        sa.ForeignKeyConstraint(["area_id"], ["area.id"], name=op.f("fk_activity_area_id_area")),
        sa.ForeignKeyConstraint(["platform_id"], ["platform.id"], name=op.f("fk_activity_platform_id_platform")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity")),
        sa.UniqueConstraint("activity_id", "platform_id", "created_at", name=op.f("uq_activity_activity_id_platform_id_created_at")),
    )
    op.create_index(
        op.f("ix_activity_activity_id"), "activity", ["activity_id"], unique=False
    )
    op.create_index(
        op.f("ix_activity_area_id"), "activity", ["area_id"], unique=False
    )
    op.create_index(
        op.f("ix_activity_platform_id"), "activity", ["platform_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop activity table
    op.drop_index(op.f("ix_activity_platform_id"), table_name="activity")
    op.drop_index(op.f("ix_activity_area_id"), table_name="activity")
    op.drop_index(op.f("ix_activity_activity_id"), table_name="activity")
    op.drop_table("activity")

    # Drop platform table
    op.drop_index(op.f("ix_platform_platform_id"), table_name="platform")
    op.drop_table("platform")

    # Drop area table
    op.drop_index(op.f("ix_area_competent_authority_id"), table_name="area")
    op.drop_index(op.f("ix_area_area_id"), table_name="area")
    op.drop_table("area")

    # Drop competent_authority table
    op.drop_index(op.f("ix_competent_authority_competent_authority_id"), table_name="competent_authority")
    op.drop_table("competent_authority")
