"""Enforce one current row per owner identity via partial unique indexes.

Revision ID: 006
Revises: 005
Create Date: 2026-06-26

Owner-versioned tables (`platform`, `competent_authority`, `area`) keep a
history of rows and treat the single row with `ended_at IS NULL` as the
"current" one. The CRUD layer looks that row up with `scalar_one_or_none()`,
so two current rows for the same identity raise `MultipleResultsFound` and the
request 500s.

Nothing in the schema forbade duplicate current rows: the existing UNIQUE
constraints include `created_at`, so two current rows with different timestamps
were allowed. This migration:

1. Heals any existing duplicate current rows by ending all but the newest
   (latest `created_at`, then highest `id`) per identity.
2. Adds a partial UNIQUE index on the current row per identity:
   - platform / competent_authority: unique `client_id` WHERE `ended_at IS NULL`
   - area: unique (`area_id`, `competent_authority_id`) WHERE `ended_at IS NULL`
     (the same area_id under different CAs stays allowed)

Partial unique indexes are supported by both PostgreSQL (production) and
SQLite (the default test database).
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import context, op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, identity columns, partial unique index name)
_OWNER_TABLES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("platform", ("client_id",), "uq_platform_current_client_id"),
    (
        "competent_authority",
        ("client_id",),
        "uq_competent_authority_current_client_id",
    ),
    ("area", ("area_id", "competent_authority_id"), "uq_area_current_area_id_ca"),
)


def _heal_duplicate_current_rows(
    table_name: str, identity_columns: tuple[str, ...]
) -> None:
    """End all but the newest current row for each identity.

    Skipped in offline mode (no live connection to read/update data).
    """
    if context.is_offline_mode():
        return

    partition_by = ", ".join(identity_columns)
    bind = op.get_bind()
    ended_at = datetime.now(UTC)
    bind.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET ended_at = :ended_at
            WHERE id IN (
                SELECT id FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY {partition_by}
                            ORDER BY created_at DESC, id DESC
                        ) AS rn
                    FROM {table_name}
                    WHERE ended_at IS NULL
                ) ranked
                WHERE ranked.rn > 1
            )
            """
        ),
        {"ended_at": ended_at},
    )


def upgrade() -> None:
    for table_name, identity_columns, index_name in _OWNER_TABLES:
        _heal_duplicate_current_rows(table_name, identity_columns)
        op.create_index(
            index_name,
            table_name,
            list(identity_columns),
            unique=True,
            postgresql_where=sa.text("ended_at IS NULL"),
            sqlite_where=sa.text("ended_at IS NULL"),
        )


def downgrade() -> None:
    for table_name, _identity_columns, index_name in reversed(_OWNER_TABLES):
        op.drop_index(index_name, table_name=table_name)
