"""Widen activity.registration_number and listing.registration_number to 128.

Revision ID: 011
Revises: 010
Create Date: 2026-10-19

Legacy registration numbers exceed 32 characters. 128 leaves room for them,
see docs/DATAMODEL_TECH.md. Listing keeps the same maximum as activity.

Widening a VARCHAR is a catalog-only change in PostgreSQL (no table rewrite).
The downgrade shrinks the columns again and fails when a row is wider than the
old limit; that is intended, data would otherwise be truncated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("activity") as batch_op:
        batch_op.alter_column(
            "registration_number",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    with op.batch_alter_table("listing") as batch_op:
        batch_op.alter_column(
            "registration_number",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("listing") as batch_op:
        batch_op.alter_column(
            "registration_number",
            existing_type=sa.String(length=128),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
    with op.batch_alter_table("activity") as batch_op:
        batch_op.alter_column(
            "registration_number",
            existing_type=sa.String(length=128),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
