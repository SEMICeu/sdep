"""Separate private client IDs from public owner functional IDs.

Revision ID: 002
Revises: 001
Create Date: 2026-05-26

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_owner_table(
    table_name: str,
    public_id_column: str,
) -> None:
    if context.is_offline_mode():
        op.execute(
            sa.text(
                f"""
                WITH owner_ids AS (
                    SELECT DISTINCT
                        {public_id_column} AS old_id,
                        lower(
                            substr(md5({public_id_column}), 1, 8) || '-' ||
                            substr(md5({public_id_column}), 9, 4) || '-' ||
                            substr(md5({public_id_column}), 13, 4) || '-' ||
                            substr(md5({public_id_column}), 17, 4) || '-' ||
                            substr(md5({public_id_column}), 21, 12)
                        ) AS new_id
                    FROM {table_name}
                )
                UPDATE {table_name}
                SET
                    client_id = owner_ids.old_id,
                    {public_id_column} = owner_ids.new_id
                FROM owner_ids
                WHERE {table_name}.{public_id_column} = owner_ids.old_id
                """
            )
        )
        return

    bind = op.get_bind()
    owner_table = sa.table(
        table_name,
        sa.column(public_id_column, sa.String(length=64)),
        sa.column("client_id", sa.String(length=64)),
    )

    old_ids = [
        row[0]
        for row in bind.execute(
            sa.select(sa.distinct(owner_table.c[public_id_column]))
        ).all()
    ]
    for old_id in old_ids:
        new_public_id = str(uuid4())
        bind.execute(
            owner_table.update()
            .where(owner_table.c[public_id_column] == old_id)
            .values(
                client_id=old_id,
                **{public_id_column: new_public_id},
            )
        )


def upgrade() -> None:
    op.add_column(
        "competent_authority",
        sa.Column("client_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "platform",
        sa.Column("client_id", sa.String(length=64), nullable=True),
    )

    _backfill_owner_table("competent_authority", "competent_authority_id")
    _backfill_owner_table("platform", "platform_id")

    with op.batch_alter_table("competent_authority") as batch_op:
        batch_op.alter_column("client_id", existing_type=sa.String(length=64), nullable=False)

    with op.batch_alter_table("platform") as batch_op:
        batch_op.alter_column("client_id", existing_type=sa.String(length=64), nullable=False)

    op.create_index(
        op.f("ix_competent_authority_client_id"),
        "competent_authority",
        ["client_id"],
        unique=False,
    )
    op.create_index(op.f("ix_platform_client_id"), "platform", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_client_id"), table_name="platform")
    op.drop_index(op.f("ix_competent_authority_client_id"), table_name="competent_authority")

    with op.batch_alter_table("platform") as batch_op:
        batch_op.drop_column("client_id")

    with op.batch_alter_table("competent_authority") as batch_op:
        batch_op.drop_column("client_id")
