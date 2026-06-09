"""Align owner table layout with DATAMODEL.

Revision ID: 004
Revises: 003
Create Date: 2026-05-27

Per DATAMODEL standard attribute layout (id, functional id, display name,
other attributes, createdAt, endedAt) and unique constraint order
(functional id, owner, version timestamp), realign `competent_authority`
and `platform`:

- Move `client_id` to sit before `created_at`/`ended_at` (physical column
  order in PostgreSQL is set by `attnum`, so we drop the trailing columns
  and re-add them in the documented order).
- Recreate UNIQUE constraints as (`<functional_id>`, `client_id`,
  `created_at`) instead of (`client_id`, `<functional_id>`, `created_at`).

Safe to drop and re-add columns because there is no production data yet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rebuild_owner_trailing_columns(
    table_name: str,
    functional_id_column: str,
    old_unique_name: str,
    new_unique_name: str,
    client_id_index_name: str,
) -> None:
    op.drop_constraint(old_unique_name, table_name, type_="unique")
    op.drop_index(client_id_index_name, table_name=table_name)
    op.drop_column(table_name, "client_id")
    op.drop_column(table_name, "ended_at")
    op.drop_column(table_name, "created_at")

    op.add_column(
        table_name,
        sa.Column("client_id", sa.String(length=64), nullable=False),
    )
    op.add_column(
        table_name,
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        table_name,
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(client_id_index_name, table_name, ["client_id"], unique=False)
    op.create_unique_constraint(
        new_unique_name,
        table_name,
        [functional_id_column, "client_id", "created_at"],
    )


def _restore_legacy_owner_layout(
    table_name: str,
    functional_id_column: str,
    new_unique_name: str,
    old_unique_name: str,
    client_id_index_name: str,
) -> None:
    op.drop_constraint(new_unique_name, table_name, type_="unique")
    op.drop_index(client_id_index_name, table_name=table_name)
    op.drop_column(table_name, "ended_at")
    op.drop_column(table_name, "created_at")
    op.drop_column(table_name, "client_id")

    op.add_column(
        table_name,
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        table_name,
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("client_id", sa.String(length=64), nullable=False),
    )
    op.create_index(client_id_index_name, table_name, ["client_id"], unique=False)
    op.create_unique_constraint(
        old_unique_name,
        table_name,
        ["client_id", functional_id_column, "created_at"],
    )


def upgrade() -> None:
    _rebuild_owner_trailing_columns(
        table_name="competent_authority",
        functional_id_column="competent_authority_id",
        old_unique_name=op.f(
            "uq_competent_authority_client_id_competent_authority_id_created_at"
        ),
        new_unique_name=op.f(
            "uq_competent_authority_ca_id_client_id_created_at"
        ),
        client_id_index_name=op.f("ix_competent_authority_client_id"),
    )
    _rebuild_owner_trailing_columns(
        table_name="platform",
        functional_id_column="platform_id",
        old_unique_name=op.f("uq_platform_client_id_platform_id_created_at"),
        new_unique_name=op.f("uq_platform_platform_id_client_id_created_at"),
        client_id_index_name=op.f("ix_platform_client_id"),
    )


def downgrade() -> None:
    _restore_legacy_owner_layout(
        table_name="platform",
        functional_id_column="platform_id",
        new_unique_name=op.f("uq_platform_platform_id_client_id_created_at"),
        old_unique_name=op.f("uq_platform_client_id_platform_id_created_at"),
        client_id_index_name=op.f("ix_platform_client_id"),
    )
    _restore_legacy_owner_layout(
        table_name="competent_authority",
        functional_id_column="competent_authority_id",
        new_unique_name=op.f(
            "uq_competent_authority_ca_id_client_id_created_at"
        ),
        old_unique_name=op.f(
            "uq_competent_authority_client_id_competent_authority_id_created_at"
        ),
        client_id_index_name=op.f("ix_competent_authority_client_id"),
    )
