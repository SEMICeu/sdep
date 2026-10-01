"""Enforce one current listing and activity row, and index the current rows.

Revision ID: 009
Revises: 008
Create Date: 2026-09-30

Same pattern as 006, now for the platform-owned tables `listing` and `activity`:

1. Heals duplicate current rows by ending all but the newest (latest
   `created_at`, then highest `id`) per (functional ID, public `platformId`).
   The public ID covers duplicates across platform versions: a platform rename
   used to leave the previous current version in place.
2. Adds a partial UNIQUE index on the current row per (functional ID,
   `platform_id`), so a concurrent first write of a new ID cannot create two.
3. Adds a partial index on (`created_at`, `id`) of the current rows, for the
   reads that page newest first.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import context, op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES: tuple[str, ...] = ("listing", "activity")


def _heal_duplicate_current_rows(table_name: str) -> None:
    """End all but the newest current row per (functional ID, public platformId).

    Skipped in offline mode (no live connection to read/update data).
    """
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET ended_at = :ended_at
            WHERE id IN (
                SELECT id FROM (
                    SELECT
                        t.id,
                        ROW_NUMBER() OVER (
                            PARTITION BY t.{table_name}_id, p.platform_id
                            ORDER BY t.created_at DESC, t.id DESC
                        ) AS rn
                    FROM {table_name} t
                    JOIN platform p ON p.id = t.platform_id
                    WHERE t.ended_at IS NULL
                ) ranked
                WHERE ranked.rn > 1
            )
            """
        ),
        {"ended_at": datetime.now(UTC)},
    )


def upgrade() -> None:
    for table_name in _TABLES:
        _heal_duplicate_current_rows(table_name)
        op.create_index(
            f"uq_{table_name}_current_{table_name}_id_platform",
            table_name,
            [f"{table_name}_id", "platform_id"],
            unique=True,
            postgresql_where=sa.text("ended_at IS NULL"),
            sqlite_where=sa.text("ended_at IS NULL"),
        )
        op.create_index(
            f"ix_{table_name}_current_created_at",
            table_name,
            ["created_at", "id"],
            postgresql_where=sa.text("ended_at IS NULL"),
            sqlite_where=sa.text("ended_at IS NULL"),
        )


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        op.drop_index(f"ix_{table_name}_current_created_at", table_name=table_name)
        op.drop_index(
            f"uq_{table_name}_current_{table_name}_id_platform", table_name=table_name
        )
