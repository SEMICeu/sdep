"""Tests for the platform service (ensure_platform)."""

from datetime import datetime

import pytest
from app.crud import platform as platform_crud
from app.exceptions.business import DuplicateResourceError, InvalidOperationError
from app.services.platform import ensure_platform
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import PlatformFactory


@pytest.mark.database
class TestEnsurePlatform:
    async def test_creates_on_first_contact(self, async_session: AsyncSession):
        platform = await ensure_platform(async_session, "client-new", "New Platform")
        assert platform.id is not None
        assert platform.platform_name == "New Platform"

    async def test_reuses_when_name_unchanged(self, async_session: AsyncSession):
        existing = await PlatformFactory.create_async(
            async_session, client_id="client-1", platform_name="Same"
        )
        platform = await ensure_platform(async_session, "client-1", "Same")
        assert platform.id == existing.id

    async def test_versions_when_name_changes(self, async_session: AsyncSession):
        existing = await PlatformFactory.create_async(
            async_session,
            client_id="client-1",
            platform_name="Old",
            created_at=datetime(2026, 1, 1),
        )
        platform = await ensure_platform(async_session, "client-1", "New")
        assert platform.id != existing.id
        assert platform.platform_id == existing.platform_id
        assert platform.platform_name == "New"
        assert (
            await platform_crud.get_by_client_id(async_session, "client-1") == platform
        )

    async def test_refuses_deactivated_platform(self, async_session: AsyncSession):
        await PlatformFactory.create_async(
            async_session, client_id="client-gone", ended_at=datetime(2026, 1, 1)
        )
        with pytest.raises(InvalidOperationError, match="has been deactivated"):
            await ensure_platform(async_session, "client-gone", "Gone")


def hide_first_lookup(monkeypatch, crud) -> None:
    """Make the first lookup of the client miss, as in a parallel first contact.

    The other request created the client between that lookup and the claim. The
    real race needs PostgreSQL, see tests/services/test_concurrent_rename.py.
    """
    real = crud.get_by_client_id
    missed: list[str] = []

    async def lookup(session, client_id):
        if not missed:
            missed.append(client_id)
            return None
        return await real(session, client_id)

    async def no_versions(session, client_id):
        return False

    monkeypatch.setattr(crud, "get_by_client_id", lookup)
    monkeypatch.setattr(crud, "exists_any_by_client_id", no_versions)


@pytest.mark.database
class TestParallelFirstContact:
    """A first contact that loses the claim reuses the platform of the winner."""

    async def test_loser_reuses_the_winner(
        self, async_session: AsyncSession, monkeypatch
    ):
        winner = await ensure_platform(async_session, "client-race", "Same")
        hide_first_lookup(monkeypatch, platform_crud)

        platform = await ensure_platform(async_session, "client-race", "Same")

        assert platform.id == winner.id

    async def test_refuses_when_no_winner_is_found(
        self, async_session: AsyncSession, monkeypatch
    ):
        await ensure_platform(async_session, "client-race-2", "Same")

        async def missing(session, client_id):
            return None

        hide_first_lookup(monkeypatch, platform_crud)
        monkeypatch.setattr(platform_crud, "get_by_client_id", missing)
        with pytest.raises(DuplicateResourceError):
            await ensure_platform(async_session, "client-race-2", "Same")
