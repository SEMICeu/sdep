"""Widen activity.url to 2048 and activity.address_full_address to 328.

Revision ID: 007
Revises: 006
Create Date: 2026-09-16

Listing URLs legitimately exceed 128 characters (query parameters).
2048 is a chosen pragmatic cap, see docs/DATAMODEL.md.
fullAddress was the sum of the other address fields (318) without room
for separators; 328 adds 5 separators of ", ".

Widening a VARCHAR is a catalog-only change in PostgreSQL (no table rewrite).
The downgrade shrinks the columns again and fails when a row is wider than the
old limit; that is intended, data would otherwise be truncated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("activity") as batch_op:
        batch_op.alter_column(
            "url",
            existing_type=sa.String(length=128),
            type_=sa.String(length=2048),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "address_full_address",
            existing_type=sa.String(length=318),
            type_=sa.String(length=328),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("activity") as batch_op:
        batch_op.alter_column(
            "address_full_address",
            existing_type=sa.String(length=328),
            type_=sa.String(length=318),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "url",
            existing_type=sa.String(length=2048),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
