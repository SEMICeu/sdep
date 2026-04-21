"""Make address_locator_designator_number optional.

Revision ID: 005
Revises: 004
Create Date: 2026-04-20

"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Relax NOT NULL on activity.address_locator_designator_number."""
    op.alter_column(
        "activity",
        "address_locator_designator_number",
        nullable=True,
    )


def downgrade() -> None:
    """Restore NOT NULL on activity.address_locator_designator_number."""
    op.alter_column(
        "activity",
        "address_locator_designator_number",
        nullable=False,
    )
