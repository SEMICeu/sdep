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
        platform_name = "Booking.com"

        # Act
        result = await platform.create(
            session=async_session,
            platform_id=platform_id,
            platform_name=platform_name,
        )

        # Assert
        assert result.id is not None
        assert result.platform_id == platform_id
        assert result.platform_name == platform_name
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_platform_with_duplicate_platform_id(
        self, async_session: AsyncSession
    ):
        """Test that creating a platform with duplicate platform_id raises IntegrityError."""
        # Arrange
        duplicate_platform_id = "duplicate-platform"

        # Create first platform
        await platform.create(
            session=async_session,
            platform_id=duplicate_platform_id,
            platform_name="First Platform",
        )
        await async_session.flush()

        # Act & Assert - Try to create second platform with same platform_id
        with pytest.raises(IntegrityError):
            await platform.create(
                session=async_session,
                platform_id=duplicate_platform_id,
                platform_name="Second Platform",
            )
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

    async def test_get_by_platform_id(self, async_session: AsyncSession):
        """Test getting a platform by platform_id string."""
        # Arrange
        test_platform_id = "test-platform-xyz"
        p = await PlatformFactory.create_async(
            async_session, platform_id=test_platform_id
        )

        # Act
        result = await platform.get_by_platform_id(async_session, test_platform_id)

        # Assert
        assert result is not None
        assert result.id == p.id
        assert result.platform_id == test_platform_id

    async def test_get_by_platform_id_not_found(self, async_session: AsyncSession):
        """Test getting a non-existent platform by platform_id."""
        # Act
        result = await platform.get_by_platform_id(
            async_session, "non-existent-platform"
        )

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
