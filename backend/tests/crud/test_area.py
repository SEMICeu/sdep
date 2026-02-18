"""Tests for Area CRUD operations."""

from datetime import datetime

import pytest
from app.crud import area
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory, CompetentAuthorityFactory


@pytest.mark.database
class TestAreaCRUD:
    """Test suite for Area CRUD operations."""

    async def test_create_area(self, async_session: AsyncSession):
        """Test creating a new area with auto-generated area_id (UUID)."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        filename = "area1.zip"
        filedata = b"binary_geo_data"

        # Act
        result = await area.create(
            async_session,
            area_id=None,
            area_name=None,
            competent_authority_id=ca.id,
            filename=filename,
            filedata=filedata,
        )

        # Assert
        assert result.id is not None
        assert isinstance(result.id, int)
        assert result.area_id is not None  # Should be auto-generated UUID
        assert len(result.area_id) == 36  # UUID format
        assert result.area_name is None  # Should be None when not provided
        assert result.competent_authority_id == ca.id
        assert result.filename == filename
        assert result.filedata == filedata
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_area_with_explicit_area_id(self, async_session: AsyncSession):
        """Test creating a new area with explicit area_id (UUID) and area_name."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        explicit_area_id = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
        area_name = "Amsterdam Central District"
        filename = "area1.zip"
        filedata = b"binary_geo_data"

        # Act
        result = await area.create(
            async_session,
            area_id=explicit_area_id,
            area_name=area_name,
            competent_authority_id=ca.id,
            filename=filename,
            filedata=filedata,
        )

        # Assert
        assert result.id is not None
        assert isinstance(result.id, int)
        assert result.area_id == explicit_area_id  # Should use provided UUID
        assert result.area_name == area_name
        assert result.competent_authority_id == ca.id
        assert result.filename == filename
        assert result.filedata == filedata
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_delete_area(self, async_session: AsyncSession):
        """Test deleting an existing area."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        a = await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )

        # Act
        result = await area.delete(async_session, a.id)

        # Assert
        assert result is True
        retrieved = await area.get_by_id(async_session, a.id)
        assert retrieved is None

    async def test_delete_area_not_found(self, async_session: AsyncSession):
        """Test deleting a non-existent area."""
        # Act
        result = await area.delete(async_session, 99999)

        # Assert
        assert result is False

    async def test_exists_area(self, async_session: AsyncSession):
        """Test checking if an area exists."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        a = await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )

        # Act
        exists = await area.exists(async_session, a.id)
        not_exists = await area.exists(async_session, 99999)

        # Assert
        assert exists is True
        assert not_exists is False

    async def test_count_areas(self, async_session: AsyncSession):
        """Test counting areas."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        for i in range(3):
            await AreaFactory.create_async(
                async_session,
                competent_authority_id=ca.id,
                filename=f"area{i}.zip",
                filedata=b"test_data",
            )

        # Act
        total = await area.count(async_session)

        # Assert
        assert total == 3

    async def test_get_all_areas(self, async_session: AsyncSession):
        """Test getting all areas."""
        # Arrange
        ca1 = await CompetentAuthorityFactory.create_async(async_session)
        ca2 = await CompetentAuthorityFactory.create_async(async_session)
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca1.id,
            filename="area1.zip",
            filedata=b"test_data1",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca2.id,
            filename="area2.zip",
            filedata=b"test_data2",
        )

        # Act
        results = await area.get_all(async_session)

        # Assert
        assert len(results) == 2

    async def test_get_all_areas_with_pagination(self, async_session: AsyncSession):
        """Test getting areas with pagination."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        for i in range(5):
            await AreaFactory.create_async(
                async_session,
                competent_authority_id=ca.id,
                filename=f"area{i}.zip",
                filedata=b"test_data",
            )

        # Act
        page1 = await area.get_all(async_session, offset=0, limit=2)
        page2 = await area.get_all(async_session, offset=2, limit=2)
        page3 = await area.get_all(async_session, offset=4, limit=2)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

    async def test_get_by_id(self, async_session: AsyncSession):
        """Test getting an area by id."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        a = await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )

        # Act
        result = await area.get_by_id(async_session, a.id)

        # Assert
        assert result is not None
        assert result.id == a.id
        assert result.competent_authority_id == ca.id

    async def test_get_by_id_not_found(self, async_session: AsyncSession):
        """Test getting a non-existent area by id."""
        # Act
        result = await area.get_by_id(async_session, 99999)

        # Assert
        assert result is None

    async def test_get_by_competent_authority_id(self, async_session: AsyncSession):
        """Test getting areas by competent authority id (foreign key)."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="area1.zip",
            filedata=b"test_data1",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="area2.zip",
            filedata=b"test_data2",
        )

        # Act
        results = await area.get_by_competent_authority_id(async_session, ca.id)

        # Assert
        assert len(results) == 2
        assert all(r.competent_authority_id == ca.id for r in results)

    async def test_get_by_competent_authority_id_not_found(
        self, async_session: AsyncSession
    ):
        """Test getting areas by non-existent competent authority id."""
        # Act
        results = await area.get_by_competent_authority_id(async_session, 99999)

        # Assert
        assert len(results) == 0

    async def test_get_by_filename(self, async_session: AsyncSession):
        """Test getting areas by filename."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        filename = "special_area.zip"
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename=filename,
            filedata=b"test_data",
        )

        # Act
        results = await area.get_by_filename(async_session, filename)

        # Assert
        assert len(results) == 1
        assert results[0].filename == filename

    async def test_get_by_area_id(self, async_session: AsyncSession):
        """Test getting area by functional area_id (UUID)."""
        # Arrange
        a = await AreaFactory.create_async(async_session)
        # Store the auto-generated ID
        generated_id = a.area_id

        # Act
        result = await area.get_by_area_id(async_session, generated_id)

        # Assert
        assert result is not None
        assert result.area_id == generated_id
        assert result.id == a.id

    async def test_get_by_area_id_not_found(self, async_session: AsyncSession):
        """Test getting area by non-existent area_id."""
        # Act
        result = await area.get_by_area_id(
            async_session, "00000000-0000-0000-0000-000000000000"
        )

        # Assert
        assert result is None

    async def test_exists_any_by_area_id_true_for_ended(
        self, async_session: AsyncSession
    ):
        """Test exists_any_by_area_id returns True for an area with ended_at set."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        await AreaFactory.create_async(
            async_session,
            area_id="ended-area-id",
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )
        await area.mark_as_ended(async_session, "ended-area-id", ca.id)

        # Act
        result = await area.exists_any_by_area_id(async_session, "ended-area-id")

        # Assert
        assert result is True

    async def test_exists_any_by_area_id_false_for_nonexistent(
        self, async_session: AsyncSession
    ):
        """Test exists_any_by_area_id returns False for non-existent area_id."""
        # Act
        result = await area.exists_any_by_area_id(
            async_session, "00000000-0000-0000-0000-000000000000"
        )

        # Assert
        assert result is False

    async def test_count_by_competent_authority_id_str(
        self, async_session: AsyncSession
    ):
        """Test counting areas by competent authority functional ID."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0518",
            competent_authority_name="Gemeente Den Haag",
        )
        for i in range(3):
            await AreaFactory.create_async(
                async_session,
                competent_authority_id=ca.id,
                filename=f"area{i}.zip",
                filedata=b"test_data",
            )

        # Act
        total = await area.count_by_competent_authority_id_str(async_session, "0518")

        # Assert
        assert total == 3

    async def test_count_by_competent_authority_id_str_not_found(
        self, async_session: AsyncSession
    ):
        """Test counting areas by non-existent competent authority functional ID."""
        # Act
        total = await area.count_by_competent_authority_id_str(async_session, "9999")

        # Assert
        assert total == 0

    async def test_get_by_area_id_and_competent_authority_id_str(
        self, async_session: AsyncSession
    ):
        """Test getting area by functional area_id and CA functional ID."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        a = await AreaFactory.create_async(
            async_session,
            area_id="test-area-lookup",
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )

        # Act
        result = await area.get_by_area_id_and_competent_authority_id_str(
            async_session, "test-area-lookup", "0363"
        )

        # Assert
        assert result is not None
        assert result.id == a.id
        assert result.area_id == "test-area-lookup"

    async def test_get_by_area_id_and_competent_authority_id_str_not_found(
        self, async_session: AsyncSession
    ):
        """Test getting area by area_id with wrong CA returns None."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await AreaFactory.create_async(
            async_session,
            area_id="test-area-wrong-ca",
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )

        # Act
        result = await area.get_by_area_id_and_competent_authority_id_str(
            async_session, "test-area-wrong-ca", "9999"
        )

        # Assert
        assert result is None

    async def test_get_by_area_id_and_competent_authority_id_str_ended(
        self, async_session: AsyncSession
    ):
        """Test getting ended area returns None."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await AreaFactory.create_async(
            async_session,
            area_id="test-area-ended",
            competent_authority_id=ca.id,
            filename="test.zip",
            filedata=b"test_data",
        )
        await area.mark_as_ended(async_session, "test-area-ended", ca.id)

        # Act
        result = await area.get_by_area_id_and_competent_authority_id_str(
            async_session, "test-area-ended", "0363"
        )

        # Assert
        assert result is None

    async def test_unique_constraint_area_id_competent_authority_id_created_at(
        self, async_session: AsyncSession
    ):
        """Test unique constraint on (area_id, competent_authority_id, created_at)."""
        import asyncio
        import uuid

        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)
        area_id = str(uuid.uuid4())

        # Act - Create first area
        a1 = await area.create(
            async_session,
            area_id=area_id,
            area_name="Version 1",
            competent_authority_id=ca.id,
            filename="area_v1.zip",
            filedata=b"data_v1",
        )
        await async_session.commit()

        # Wait to ensure different timestamp (1 second to guarantee SQLite timestamp difference)
        await asyncio.sleep(1.0)

        # Act - Create second area with same area_id (should work due to different created_at)
        a2 = await area.create(
            async_session,
            area_id=area_id,
            area_name="Version 2",
            competent_authority_id=ca.id,
            filename="area_v2.zip",
            filedata=b"data_v2",
        )

        # Assert
        assert a1.area_id == a2.area_id
        assert a1.id != a2.id  # Different technical IDs
        assert a1.created_at != a2.created_at  # Different timestamps
