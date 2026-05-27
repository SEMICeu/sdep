"""Key owner version uniqueness on private client IDs plus public IDs.

Revision ID: 003
Revises: 002
Create Date: 2026-05-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("competent_authority") as batch_op:
        batch_op.drop_constraint(
            op.f("uq_competent_authority_competent_authority_id_created_at"),
            type_="unique",
        )
        batch_op.create_unique_constraint(
            op.f(
                "uq_competent_authority_client_id_competent_authority_id_created_at"
            ),
            ["client_id", "competent_authority_id", "created_at"],
        )

    with op.batch_alter_table("platform") as batch_op:
        batch_op.drop_constraint(
            op.f("uq_platform_platform_id_created_at"),
            type_="unique",
        )
        batch_op.create_unique_constraint(
            op.f("uq_platform_client_id_platform_id_created_at"),
            ["client_id", "platform_id", "created_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("platform") as batch_op:
        batch_op.drop_constraint(
            op.f("uq_platform_client_id_platform_id_created_at"),
            type_="unique",
        )
        batch_op.create_unique_constraint(
            op.f("uq_platform_platform_id_created_at"),
            ["platform_id", "created_at"],
        )

    with op.batch_alter_table("competent_authority") as batch_op:
        batch_op.drop_constraint(
            op.f(
                "uq_competent_authority_client_id_competent_authority_id_created_at"
            ),
            type_="unique",
        )
        batch_op.create_unique_constraint(
            op.f("uq_competent_authority_competent_authority_id_created_at"),
            ["competent_authority_id", "created_at"],
        )
