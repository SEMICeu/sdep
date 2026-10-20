"""CRUD operations for the identity tables (see app/models/identity.py).

A write first claims the functional IDs it touches: new IDs get the caller as
owner, every ID is locked, and the caller compares the returned owners with
itself. The identity row is the versioning lock for its resource.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import (
    CompetentAuthorityIdentity,
    IdentityModel,
    PlatformIdentity,
)


async def claim(
    session: AsyncSession,
    model: IdentityModel,
    ids: Iterable[str],
    owner: str,
) -> dict[str, str]:
    """
    Record `owner` for the IDs that are new, lock all IDs, and return their owners.

    An existing ID keeps its owner. IDs are inserted and locked in sorted order,
    so concurrent writers wait for each other instead of deadlocking.

    Args:
        session: Async database session
        model: Identity model, e.g. AreaIdentity
        ids: Functional IDs of the write
        owner: Functional ID (or client ID) of the caller

    Returns:
        Dictionary {functional_id: owner} for every ID
    """
    sorted_ids = sorted(set(ids))
    if not sorted_ids:
        return {}

    dialect_insert = (
        postgresql.insert
        if session.get_bind().dialect.name == "postgresql"
        else sqlite.insert
    )
    await session.execute(
        dialect_insert(model)
        .values([{model.id_column: i, model.owner_column: owner} for i in sorted_ids])
        .on_conflict_do_nothing()
    )

    id_col = getattr(model, model.id_column)
    owner_col = getattr(model, model.owner_column)
    stmt = (
        select(id_col, owner_col)
        .where(id_col.in_(sorted_ids))
        .order_by(id_col)
        .with_for_update()
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}


async def lock_client(
    session: AsyncSession,
    model: type[CompetentAuthorityIdentity] | type[PlatformIdentity],
    client_id: str,
) -> None:
    """
    Lock the identity row of a client, if it has one, to version its CA or platform.

    The identity row is never ended, so a writer that waited for a concurrent
    rename still finds it, and then reads the new current version. FOR NO KEY
    UPDATE: rows that reference the identity (new area or activity IDs) do not wait.

    Args:
        session: Async database session
        model: CompetentAuthorityIdentity or PlatformIdentity
        client_id: Private authentication client ID
    """
    await session.execute(
        select(model.client_id)
        .where(model.client_id == client_id)
        .with_for_update(key_share=True)
    )
