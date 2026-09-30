"""Tests for the platform service (ensure_platform)."""

from datetime import datetime

import pytest
from app.crud import platform as platform_crud
from app.exceptions.business import InvalidOperationError
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
