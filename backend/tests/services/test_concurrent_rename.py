"""Concurrent writes that must wait for each other (PostgreSQL only).

Renames and first contacts of a CA or platform, and identical resends of a record.

A rename ends the current version row. A second writer must wait on the identity
row and then reuse the new version, see crud/identity.py (lock_client).
Run by `make test-migrations` (PostgreSQL); `make test` (SQLite) skips them.
"""

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from app.crud import competent_authority as ca_crud
from app.crud import platform as platform_crud
from app.models.activity import Activity
from app.services.activity_bulk import create_activities_bulk
from app.services.area import create_area
from app.services.platform import ensure_platform
from sqlalchemy import func, select
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


async def test_parallel_first_contact_of_a_platform_shares_one_platform(
    async_engine: AsyncEngine,
):
    """The second first contact waits on the claim, then reuses the new platform."""
    sessions = _sessions(async_engine)
    first: list[str] = []

    async def write(session: AsyncSession):
        platform = await ensure_platform(session, "race-new-platform", "New")
        first.append(platform.platform_id)
        return platform

    platform = await _second_waits_for_first(sessions, write)

    assert platform.platform_id == first[0]


async def test_parallel_first_uploads_of_a_ca_share_one_ca(async_engine: AsyncEngine):
    """The second first upload waits on the CA claim, then reuses the new CA."""
    sessions = _sessions(async_engine)
    calls = iter(["race-new-1", "race-new-2"])
    first: list[str] = []

    async def write(session: AsyncSession):
        area_id = next(calls)
        created = await create_area(
            session=session,
            area_id=area_id,
            area_name=None,
            filename=f"{area_id}.zip",
            filedata=b"data",
            client_id="race-new-ca",
            competent_authority_name="New",
        )
        first.append(created.competent_authority.competent_authority_id)
        return created

    area = await _second_waits_for_first(sessions, write)

    assert area.competent_authority.competent_authority_id == first[0]


@pytest.mark.parametrize("activity_id", [None, "race-resend"], ids=["generated", "own"])
async def test_parallel_identical_resends_store_one_version(
    async_engine: AsyncEngine, activity_id: str | None
):
    """A resend while the first request still runs waits, then gets the stored one."""
    sessions = _sessions(async_engine)
    area_id = f"race-resend-area-{activity_id is None}"
    async with sessions() as session:
        await create_area(
            session=session,
            area_id=area_id,
            area_name=None,
            filename="race.zip",
            filedata=b"data",
            client_id="race-resend-ca",
            competent_authority_name="CA",
        )
        await ensure_platform(session, "race-resend-str", "STR")
        await session.commit()

    item = {
        "areaId": area_id,
        "url": "http://example.com/race",
        "registrationNumber": "REG-1",
        "address": {
            "thoroughfare": "Street",
            "postCode": "1234AB",
            "postName": "City",
            "fullAddress": "Street, 1234AB City",
        },
        "numberOfGuests": 1,
        "countryOfGuests": ["NLD"],
        "temporal": {
            "startDatetime": "2025-06-01T14:00:00Z",
            "endDatetime": "2025-06-07T11:00:00Z",
        },
    }
    if activity_id is not None:
        item["activityId"] = activity_id
    first: list = []

    async def write(session: AsyncSession):
        response = await create_activities_bulk(
            session, [dict(item)], "race-resend-str", "STR"
        )
        first.append(response.results[0].activity)
        return response.results[0].activity

    second = await _second_waits_for_first(sessions, write)

    assert second is not None and first[0] is not None
    assert (second.activity_id, second.created_at) == (
        first[0].activity_id,
        first[0].created_at,
    )
    async with sessions() as session:
        count = await session.scalar(
            select(func.count()).where(Activity.activity_id == second.activity_id)
        )
        assert count == 1
