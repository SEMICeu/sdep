"""Tests for Platform CRUD operations."""

from datetime import datetime

import pytest
from app.crud import platform
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import PlatformFactory


@pytest.mark.database
class TestPlatformCRUD:
    """Test suite for Platform CRUD operations."""

    async def test_create_platform(self, async_session: AsyncSession):
        """Test creating a new platform."""
        # Arrange
        platform_id = "platform01"
        platform_name = "Example.com"

        # Act
        result = await platform.create(
            session=async_session,
            client_id="platform01-client",
            platform_id=platform_id,
            platform_name=platform_name,
        )

        # Assert
        assert result.id is not None
        assert result.client_id == "platform01-client"
        assert result.platform_id == platform_id
        assert result.platform_name == platform_name
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_platform_allows_duplicate_platform_id(
        self, async_session: AsyncSession
    ):
        """Test that duplicate public platform_id values are allowed."""
        # Arrange
        duplicate_platform_id = "duplicate-platform"

        # Create first platform
        await platform.create(
            session=async_session,
            client_id="duplicate-platform-client-1",
            platform_id=duplicate_platform_id,
            platform_name="First Platform",
        )
        await async_session.flush()

        # Act
        second = await platform.create(
            session=async_session,
            client_id="duplicate-platform-client-2",
            platform_id=duplicate_platform_id,
            platform_name="Second Platform",
        )
        await async_session.flush()

        # Assert
        assert second.platform_id == duplicate_platform_id

    async def test_create_platform_with_duplicate_client_id_created_at(
        self, async_session: AsyncSession
    ):
        """Test same client can create different public IDs at the same created_at."""
        # Arrange
        created_at = datetime(2026, 1, 1)

        await platform.create(
            session=async_session,
            client_id="duplicate-platform-client",
            platform_id="duplicate-platform-1",
            platform_name="First Platform",
        )
        first = await platform.get_by_client_id(
            async_session,
            "duplicate-platform-client",
        )
        assert first is not None
        first.created_at = created_at
        await async_session.flush()

        # Act
        second = await platform.create(
            session=async_session,
            client_id="duplicate-platform-client",
            platform_id="duplicate-platform-2",
            platform_name="Second Platform",
        )
        second.created_at = created_at
        await async_session.flush()

        # Assert
        assert second.client_id == first.client_id
        assert second.platform_id != first.platform_id

    async def test_create_platform_with_duplicate_client_public_id_created_at(
        self, async_session: AsyncSession
    ):
        """Test duplicate public IDs within the same client/version raise IntegrityError."""
        # Arrange
        created_at = datetime(2026, 1, 1)

        await platform.create(
            session=async_session,
            client_id="duplicate-platform-client",
            platform_id="duplicate-platform",
            platform_name="First Platform",
        )
        first = await platform.get_by_client_id(
            async_session,
            "duplicate-platform-client",
        )
        assert first is not None
        first.created_at = created_at
        await async_session.flush()

        # Act & Assert
        with pytest.raises(IntegrityError):
            second = await platform.create(
                session=async_session,
                client_id="duplicate-platform-client",
                platform_id="duplicate-platform",
                platform_name="Second Platform",
            )
            second.created_at = created_at
            await async_session.flush()

    async def test_get_by_id(self, async_session: AsyncSession):
        """Test getting a platform by id."""
        # Arrange
        p = await PlatformFactory.create_async(async_session)

        # Act
        result = await platform.get_by_id(async_session, p.id)

        # Assert
        assert result is not None
        assert result.id == p.id
        assert result.platform_id == p.platform_id
        assert result.platform_name == p.platform_name

    async def test_get_by_id_not_found(self, async_session: AsyncSession):
        """Test getting a non-existent platform by id."""
        # Act
        result = await platform.get_by_id(async_session, 99999)

        # Assert
        assert result is None

    async def test_get_all_platforms(self, async_session: AsyncSession):
        """Test getting all platforms."""
        # Arrange
        await PlatformFactory.create_async(
            async_session, platform_id="platform01", platform_name="Platform One"
        )
        await PlatformFactory.create_async(
            async_session, platform_id="platform02", platform_name="Platform Two"
        )
        await PlatformFactory.create_async(
            async_session, platform_id="platform03", platform_name="Platform Three"
        )

        # Act
        results = await platform.get_all(async_session)

        # Assert
        assert len(results) == 3
        platform_ids = {p.platform_id for p in results}
        assert "platform01" in platform_ids
        assert "platform02" in platform_ids
        assert "platform03" in platform_ids

    async def test_get_all_platforms_empty(self, async_session: AsyncSession):
        """Test getting all platforms when database is empty."""
        # Act
        results = await platform.get_all(async_session)

        # Assert
        assert len(results) == 0

    async def test_count_platforms(self, async_session: AsyncSession):
        """Test counting platforms."""
        # Arrange
        await PlatformFactory.create_async(async_session)
        await PlatformFactory.create_async(async_session)
        await PlatformFactory.create_async(async_session)

        # Act
        total = await platform.count(async_session)

        # Assert
        assert total == 3

    async def test_count_platforms_empty(self, async_session: AsyncSession):
        """Test counting platforms when database is empty."""
        # Act
        total = await platform.count(async_session)

        # Assert
        assert total == 0

    async def test_exists_true(self, async_session: AsyncSession):
        created = await PlatformFactory.create_async(
            async_session, platform_id="exists-me"
        )
        assert await platform.exists(async_session, created.id) is True

    async def test_exists_false(self, async_session: AsyncSession):
        assert await platform.exists(async_session, 99999) is False

    async def test_get_by_client_id_found(self, async_session: AsyncSession):
        """Test getting a current platform by client_id."""
        created = await platform.create(
            async_session,
            client_id="client-abc",
            platform_name="My Platform",
        )

        result = await platform.get_by_client_id(async_session, "client-abc")

        assert result is not None
        assert result.id == created.id
        assert result.client_id == "client-abc"

    async def test_get_by_client_id_not_found(self, async_session: AsyncSession):
        """Test get_by_client_id returns None when client_id does not exist."""
        result = await platform.get_by_client_id(async_session, "no-such-client")

        assert result is None

    async def test_get_by_client_id_returns_none_when_ended(
        self, async_session: AsyncSession
    ):
        """Test get_by_client_id returns None for a soft-deleted (ended) platform."""
        created = await platform.create(
            async_session,
            client_id="ended-client",
            platform_name="Ended Platform",
        )
        await platform.mark_as_ended(async_session, created.platform_id)

        result = await platform.get_by_client_id(async_session, "ended-client")

        assert result is None

    async def test_exists_any_by_client_id_true_for_ended(
        self, async_session: AsyncSession
    ):
        """Test exists_any_by_client_id returns True even after the platform is ended."""
        created = await platform.create(
            async_session,
            client_id="client-ended",
            platform_name="Ended Platform",
        )
        await platform.mark_as_ended(async_session, created.platform_id)

        assert (
            await platform.exists_any_by_client_id(async_session, "client-ended")
            is True
        )

    async def test_exists_any_by_client_id_false_for_nonexistent(
        self, async_session: AsyncSession
    ):
        """Test exists_any_by_client_id returns False for unknown client_id."""
        assert (
            await platform.exists_any_by_client_id(async_session, "no-such-client-id")
            is False
        )

    async def test_mark_as_ended_by_client_id(self, async_session: AsyncSession):
        """Test that mark_as_ended_by_client_id sets ended_at on the current record."""
        created = await platform.create(
            async_session,
            client_id="client-to-end",
            platform_name="Platform To End",
        )
        assert created.ended_at is None

        await platform.mark_as_ended_by_client_id(async_session, "client-to-end")
        await async_session.refresh(created)

        assert created.ended_at is not None
