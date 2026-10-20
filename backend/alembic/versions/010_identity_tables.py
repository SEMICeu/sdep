"""Add identity tables: one owner per functional ID, across all versions.

Revision ID: 010
Revises: 009
Create Date: 2026-10-08

Every versioned class gets an identity table with one row per functional ID
and its owner (see app/models/identity.py):

1. Creates `competent_authority_identity`, `platform_identity` (owner: the
   private `client_id`), `area_identity` (owner: `competentAuthorityId`),
   `listing_identity` and `activity_identity` (owner: `platformId`).
2. Fills them from the existing rows. Stops when an ID has more than one owner,
   or a client more than one public ID: that data needs a decision first.
3. Narrows the version constraints of `area`, `listing` and `activity` to the
   functional ID: UNIQUE (`<class>_id`, `created_at`) and one current row per
   `<class>_id`. The plain `<class>_id` index goes, the unique ones cover it.
4. Adds a foreign key from every version table to its identity table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (identity table, functional ID, owner column, owner FK target or None)
_IDENTITIES: tuple[tuple[str, str, str, str | None], ...] = (
    ("competent_authority_identity", "competent_authority_id", "client_id", None),
    ("platform_identity", "platform_id", "client_id", None),
    (
        "area_identity",
        "area_id",
        "competent_authority_id",
        "competent_authority_identity.competent_authority_id",
    ),
    ("listing_identity", "listing_id", "platform_id", "platform_identity.platform_id"),
    (
        "activity_identity",
        "activity_id",
        "platform_id",
        "platform_identity.platform_id",
    ),
)

# Rows per functional ID with its owner's functional ID, for the backfill
_OWNED_ROWS: dict[str, str] = {
    "competent_authority_identity": (
        "SELECT competent_authority_id AS fid, client_id AS owner, created_at "
        "FROM competent_authority"
    ),
    "platform_identity": (
        "SELECT platform_id AS fid, client_id AS owner, created_at FROM platform"
    ),
    "area_identity": (
        "SELECT a.area_id AS fid, o.competent_authority_id AS owner, a.created_at "
        "FROM area a JOIN competent_authority o ON o.id = a.competent_authority_id"
    ),
    "listing_identity": (
        "SELECT t.listing_id AS fid, o.platform_id AS owner, t.created_at "
        "FROM listing t JOIN platform o ON o.id = t.platform_id"
    ),
    "activity_identity": (
        "SELECT t.activity_id AS fid, o.platform_id AS owner, t.created_at "
        "FROM activity t JOIN platform o ON o.id = t.platform_id"
    ),
}

# Version tables whose constraints narrow to the functional ID
_VERSIONED: tuple[tuple[str, str], ...] = (
    ("area", "uq_area_area_id_competent_authority_id_created_at"),
    ("listing", "uq_listing_listing_id_platform_id_created_at"),
    ("activity", "uq_activity_activity_id_platform_id_created_at"),
)
_OLD_CURRENT_INDEX: dict[str, tuple[str, list[str]]] = {
    "area": ("uq_area_current_area_id_ca", ["area_id", "competent_authority_id"]),
    "listing": ("uq_listing_current_listing_id_platform", ["listing_id", "platform_id"]),
    "activity": (
        "uq_activity_current_activity_id_platform",
        ["activity_id", "platform_id"],
    ),
}

# Owner version tables: their public ID references the identity table
_OWNERS: tuple[tuple[str, str], ...] = (
    ("competent_authority", "competent_authority_id"),
    ("platform", "platform_id"),
)


def _backfill(table_name: str, fid: str, owner: str) -> None:
    """Insert one identity row per functional ID, refusing shared IDs.

    Skipped in offline mode (no live connection to read data).
    """
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    rows = _OWNED_ROWS[table_name]
    shared = bind.execute(
        sa.text(
            f"SELECT fid FROM ({rows}) r GROUP BY fid HAVING COUNT(DISTINCT owner) > 1"
        )
    ).fetchall()
    if shared:
        ids = ", ".join(str(row[0]) for row in shared[:10])
        raise RuntimeError(f"{table_name}: IDs with more than one owner: {ids}")
    if owner == "client_id":
        clients = bind.execute(
            sa.text(
                f"SELECT owner FROM ({rows}) r GROUP BY owner "
                "HAVING COUNT(DISTINCT fid) > 1"
            )
        ).fetchall()
        if clients:
            raise RuntimeError(
                f"{table_name}: {len(clients)} client(s) with more than one public ID"
            )
    bind.execute(
        sa.text(
            f"INSERT INTO {table_name} ({fid}, {owner}, created_at) "
            f"SELECT fid, MIN(owner), MIN(created_at) FROM ({rows}) r GROUP BY fid"
        )
    )


def upgrade() -> None:
    for table_name, fid, owner, owner_fk in _IDENTITIES:
        owner_column = (
            sa.Column(owner, sa.String(length=64), nullable=False, unique=True)
            if owner_fk is None
            else sa.Column(
                owner,
                sa.String(length=64),
                sa.ForeignKey(owner_fk, name=op.f(f"fk_{table_name}_{owner}_{owner_fk.split('.')[0]}")),
                nullable=False,
            )
        )
        op.create_table(
            table_name,
            sa.Column(fid, sa.String(length=64), nullable=False),
            owner_column,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint(fid, name=op.f(f"pk_{table_name}")),
        )
        if owner_fk is not None:
            op.create_index(
                op.f(f"ix_{table_name}_{owner}"), table_name, [owner], unique=False
            )
        _backfill(table_name, fid, owner)

    for table_name, old_unique in _VERSIONED:
        fid = f"{table_name}_id"
        old_index, _old_columns = _OLD_CURRENT_INDEX[table_name]
        op.drop_index(old_index, table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_{fid}"), table_name=table_name)
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(old_unique, type_="unique")
            batch_op.create_unique_constraint(
                op.f(f"uq_{table_name}_{fid}_created_at"), [fid, "created_at"]
            )
            batch_op.create_foreign_key(
                op.f(f"fk_{table_name}_{fid}_{table_name}_identity"),
                f"{table_name}_identity",
                [fid],
                [fid],
            )
        op.create_index(
            f"uq_{table_name}_current_{fid}",
            table_name,
            [fid],
            unique=True,
            postgresql_where=sa.text("ended_at IS NULL"),
            sqlite_where=sa.text("ended_at IS NULL"),
        )

    for table_name, fid in _OWNERS:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_foreign_key(
                op.f(f"fk_{table_name}_{fid}_{table_name}_identity"),
                f"{table_name}_identity",
                [fid],
                [fid],
            )


def downgrade() -> None:
    for table_name, fid in reversed(_OWNERS):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(
                op.f(f"fk_{table_name}_{fid}_{table_name}_identity"),
                type_="foreignkey",
            )

    for table_name, old_unique in reversed(_VERSIONED):
        fid = f"{table_name}_id"
        old_index, old_columns = _OLD_CURRENT_INDEX[table_name]
        op.drop_index(f"uq_{table_name}_current_{fid}", table_name=table_name)
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(
                op.f(f"fk_{table_name}_{fid}_{table_name}_identity"),
                type_="foreignkey",
            )
            batch_op.drop_constraint(
                op.f(f"uq_{table_name}_{fid}_created_at"), type_="unique"
            )
            batch_op.create_unique_constraint(
                old_unique, [*old_columns, "created_at"]
            )
        op.create_index(
            op.f(f"ix_{table_name}_{fid}"), table_name, [fid], unique=False
        )
        op.create_index(
            old_index,
            table_name,
            old_columns,
            unique=True,
            postgresql_where=sa.text("ended_at IS NULL"),
            sqlite_where=sa.text("ended_at IS NULL"),
        )

    for table_name, _fid, _owner, _owner_fk in reversed(_IDENTITIES):
        op.drop_table(table_name)
