"""Concurrent renames of a CA or platform: they wait for each other (PostgreSQL only).

A rename ends the current version row. A second writer must wait on the identity
row and then reuse the new version, see crud/identity.py (lock_client).
Run by `make test-migrations` (PostgreSQL); `make test` (SQLite) skips them.
"""

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from app.crud import competent_authority as ca_crud
from app.crud import platform as platform_crud
from app.services.area import create_area
from app.services.platform import ensure_platform
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.database


def _sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    if engine.dialect.name != "postgresql":
        pytest.skip("Row locks need PostgreSQL (set DATABASE_URL)")
    return async_sessionmaker(engine, expire_on_commit=False)


async def _second_waits_for_first[T](
    sessions: async_sessionmaker[AsyncSession],
    write: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    """Run `write` in two transactions: the second must wait until the first commits."""
    async with sessions() as first:
        await write(first)

        async def second() -> T:
            async with sessions() as session:
                result = await write(session)
                await session.commit()
                return result

        task = asyncio.create_task(second())
        await asyncio.sleep(0.5)
        assert not task.done(), "the second rename did not wait for the first"
        await first.commit()
    return await asyncio.wait_for(task, timeout=10)


async def test_concurrent_platform_renames_create_one_version(
    async_engine: AsyncEngine,
):
    sessions = _sessions(async_engine)
    async with sessions() as session:
        old = await ensure_platform(session, "race-platform", "Old")
        await session.commit()

    platform = await _second_waits_for_first(
        sessions, lambda s: ensure_platform(s, "race-platform", "New")
    )

    assert (platform.platform_id, platform.platform_name) == (old.platform_id, "New")
    async with sessions() as session:
        current = await platform_crud.get_by_client_id(session, "race-platform")
        assert current is not None and current.id == platform.id


async def test_concurrent_ca_renames_create_one_version(async_engine: AsyncEngine):
    sessions = _sessions(async_engine)

    def post_area(area_id: str, name: str):
        return lambda s: create_area(
            session=s,
            area_id=area_id,
            area_name=None,
            filename=f"{area_id}.zip",
            filedata=b"data",
            client_id="race-ca",
            competent_authority_name=name,
        )

    async with sessions() as session:
        old = await post_area("race-area-0", "Old")(session)
        await session.commit()

    calls = iter(["race-area-1", "race-area-2"])
    area = await _second_waits_for_first(
        sessions, lambda s: post_area(next(calls), "New")(s)
    )

    ca = area.competent_authority
    assert (ca.competent_authority_id, ca.competent_authority_name) == (
        old.competent_authority.competent_authority_id,
        "New",
    )
    async with sessions() as session:
        current = await ca_crud.get_by_client_id(session, "race-ca")
        assert current is not None and current.id == ca.id
