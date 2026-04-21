"""Add lifecycle status to activity.

Revision ID: 008
Revises: 007
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


activity_status_enum = postgresql.ENUM(
    "finished",
    "cancelled",
    name="activitystatus",
    create_type=False,
)


def upgrade() -> None:
    """Add activity.status with a default backfill of 'finished'."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        activity_status_enum.create(bind, checkfirst=True)
        status_type = activity_status_enum
        server_default = sa.text("'finished'::activitystatus")
    else:
        status_type = sa.String(length=16)
        server_default = sa.text("'finished'")

    op.add_column(
        "activity",
        sa.Column(
            "status",
            status_type,
            nullable=False,
            server_default=server_default,
        ),
    )
    op.alter_column("activity", "status", server_default=None)


def downgrade() -> None:
    """Remove activity.status."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_column("activity", "status")

    if is_postgres:
        activity_status_enum.drop(bind, checkfirst=True)
