"""Tests for Area business service"""

import pytest
from app.exceptions.business import InvalidOperationError, ResourceNotFoundError
from app.services import area
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory


@pytest.mark.database
class TestAreaService:
    """Test suite for Area business service"""

    async def test_get_areas_empty(self, async_session: AsyncSession):
        """Test getting areas when database is empty"""
        # Act
        result = await area.get_areas(async_session)

        # Assert
        assert result == []

    async def test_get_areas_single_area(self, async_session: AsyncSession):
        """Test getting a single area"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Act
        result = await area.get_areas(async_session)

        # Assert
        assert len(result) == 1
        assert result[0]["competentAuthorityId"] == "0363"
        assert result[0]["competentAuthorityName"] == "Gemeente Amsterdam"
        assert "areaId" in result[0]
        assert "filename" in result[0]
        assert "createdAt" in result[0]

    async def test_get_areas_multiple_areas(self, async_session: AsyncSession):
        """Test getting multiple areas"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0599",
            competent_authority_name="Gemeente Rotterdam",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0518",
            competent_authority_name="Gemeente Den Haag",
        )

        # Act
        result = await area.get_areas(async_session)

        # Assert
        assert len(result) == 3

        # Find each area in results
        area1 = next((a for a in result if a["competentAuthorityId"] == "0363"), None)
        area2 = next((a for a in result if a["competentAuthorityId"] == "0599"), None)
        area3 = next((a for a in result if a["competentAuthorityId"] == "0518"), None)

        assert area1 is not None
        assert area1["competentAuthorityName"] == "Gemeente Amsterdam"

        assert area2 is not None
        assert area2["competentAuthorityName"] == "Gemeente Rotterdam"

        assert area3 is not None
        assert area3["competentAuthorityName"] == "Gemeente Den Haag"

    async def test_get_areas_multiple_areas_same_authority(
        self, async_session: AsyncSession
    ):
        """Test getting multiple areas from the same competent authority"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Act
        result = await area.get_areas(async_session)

        # Assert
        assert len(result) == 3
        for area_dict in result:
            assert area_dict["competentAuthorityId"] == "0363"
            assert area_dict["competentAuthorityName"] == "Gemeente Amsterdam"

    async def test_get_areas_response_structure(self, async_session: AsyncSession):
        """Test that response structure matches specification"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="TEST",
            competent_authority_name="Test Authority",
        )

        # Act
        result = await area.get_areas(async_session)

        # Assert
        assert len(result) == 1
        area_dict = result[0]

        # Verify all required keys are present
        assert "areaId" in area_dict
        assert "areaName" in area_dict
        assert "competentAuthorityId" in area_dict
        assert "competentAuthorityName" in area_dict
        assert "filename" in area_dict
        assert "createdAt" in area_dict

        # Verify no extra keys
        assert set(area_dict.keys()) == {
            "areaId",
            "areaName",
            "competentAuthorityId",
            "competentAuthorityName",
            "filename",
            "createdAt",
        }

        # Verify types
        assert isinstance(area_dict["areaId"], str)
        assert len(area_dict["areaId"]) == 36  # UUID format
        assert isinstance(area_dict["areaName"], str) or area_dict["areaName"] is None
        assert isinstance(area_dict["competentAuthorityId"], str)
        assert isinstance(area_dict["competentAuthorityName"], str)
        assert isinstance(area_dict["filename"], str)

    async def test_get_areas_with_pagination_offset(self, async_session: AsyncSession):
        """Test getting areas with offset pagination"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0001",
            competent_authority_name="CA 1",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0002",
            competent_authority_name="CA 2",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0003",
            competent_authority_name="CA 3",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0004",
            competent_authority_name="CA 4",
        )

        # Act
        result = await area.get_areas(async_session, offset=2)

        # Assert
        assert len(result) == 2
        ids = {area["competentAuthorityId"] for area in result}
        assert "0003" in ids
        assert "0004" in ids

    async def test_get_areas_with_pagination_limit(self, async_session: AsyncSession):
        """Test getting areas with limit pagination"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0001",
            competent_authority_name="CA 1",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0002",
            competent_authority_name="CA 2",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0003",
            competent_authority_name="CA 3",
        )

        # Act
        result = await area.get_areas(async_session, limit=2)

        # Assert
        assert len(result) == 2

    async def test_get_areas_with_pagination_offset_and_limit(
        self, async_session: AsyncSession
    ):
        """Test getting areas with both offset and limit pagination"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0001",
            competent_authority_name="CA 1",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0002",
            competent_authority_name="CA 2",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0003",
            competent_authority_name="CA 3",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0004",
            competent_authority_name="CA 4",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0005",
            competent_authority_name="CA 5",
        )

        # Act
        result = await area.get_areas(async_session, offset=1, limit=2)

        # Assert: verify pagination returns correct count and valid IDs.
        # We don't assert specific IDs because all areas are created with
        # near-identical timestamps, making order_by(created_at.desc()) non-deterministic.
        assert len(result) == 2
        all_ids = {"0001", "0002", "0003", "0004", "0005"}
        ids = {area["competentAuthorityId"] for area in result}
        assert ids.issubset(all_ids)

    async def test_get_areas_pagination_offset_beyond_results(
        self, async_session: AsyncSession
    ):
        """Test pagination with offset beyond available results"""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0001",
            competent_authority_name="CA 1",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="0002",
            competent_authority_name="CA 2",
        )

        # Act
        result = await area.get_areas(async_session, offset=10)

        # Assert
        assert len(result) == 0

    async def test_count_areas_empty(self, async_session: AsyncSession):
        """Test counting areas when database is empty"""
        # Act
        result = await area.count_areas(async_session)

        # Assert
        assert result == 0

    async def test_count_areas_single(self, async_session: AsyncSession):
        """Test counting areas with single area"""
        # Arrange
        await AreaFactory.create_async(async_session)

        # Act
        result = await area.count_areas(async_session)

        # Assert
        assert result == 1

    async def test_count_areas_multiple(self, async_session: AsyncSession):
        """Test counting areas with multiple areas"""
        # Arrange
        await AreaFactory.create_async(async_session)
        await AreaFactory.create_async(async_session)
        await AreaFactory.create_async(async_session)
        await AreaFactory.create_async(async_session)
        await AreaFactory.create_async(async_session)

        # Act
        result = await area.count_areas(async_session)

        # Assert
        assert result == 5

    # Tests for create_area

    async def test_create_area_success(self, async_session: AsyncSession):
        """Test creating a single area"""
        # Act
        area_obj = await area.create_area(
            session=async_session,
            area_id="test-area-001",
            area_name="Test Area",
            filename="TestArea.zip",
            filedata=b"data1",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert
        assert area_obj.area_id == "test-area-001"
        assert area_obj.area_name == "Test Area"
        assert area_obj.filename == "TestArea.zip"
        assert area_obj.filedata == b"data1"

        count = await area.count_areas(async_session)
        assert count == 1

    async def test_create_area_auto_generates_id(self, async_session: AsyncSession):
        """Test that area_id is auto-generated when None"""
        # Act
        area_obj = await area.create_area(
            session=async_session,
            area_id=None,
            area_name=None,
            filename="AutoId.zip",
            filedata=b"data",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert
        assert area_obj.area_id is not None
        assert len(area_obj.area_id) == 36  # UUID format

    async def test_create_area_creates_competent_authority(
        self, async_session: AsyncSession
    ):
        """Test that competent authority is created if it doesn't exist"""
        # Act
        await area.create_area(
            session=async_session,
            area_id="new-ca-area",
            area_name=None,
            filename="NewCA.zip",
            filedata=b"data",
            competent_authority_id_str="8888",
            competent_authority_name="Test Authority",
        )

        # Assert
        from app.crud import competent_authority as ca_crud

        ca = await ca_crud.get_by_competent_authority_id(async_session, "8888")
        assert ca is not None
        assert ca.competent_authority_name == "Test Authority"

    async def test_create_area_versions_competent_authority(
        self, async_session: AsyncSession
    ):
        """Test that existing competent authority is versioned (old ended, new created)"""
        import asyncio

        # Arrange - create first area (creates CA)
        await area.create_area(
            session=async_session,
            area_id="area-1",
            area_name=None,
            filename="Area1.zip",
            filedata=b"data1",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Wait to ensure different timestamp (SQLite second precision)
        await asyncio.sleep(1.0)

        # Act - create second area (should version CA: mark old as ended, create new)
        await area.create_area(
            session=async_session,
            area_id="area-2",
            area_name=None,
            filename="Area2.zip",
            filedata=b"data2",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert
        from app.models.competent_authority import CompetentAuthority
        from sqlalchemy import select

        cas = await async_session.execute(select(CompetentAuthority))
        all_cas = cas.scalars().all()
        assert len(all_cas) == 2  # Two CA versions (old ended, new current)

        # Only one current CA (ended_at IS NULL)
        current_cas = [ca for ca in all_cas if ca.ended_at is None]
        assert len(current_cas) == 1

        area_count = await area.count_areas(async_session)
        assert area_count == 2  # Two areas

    async def test_create_area_versioning_marks_previous_as_ended(
        self, async_session: AsyncSession
    ):
        """Test creating area with same areaId marks previous version as ended"""
        import asyncio

        # Arrange - create first version
        await area.create_area(
            session=async_session,
            area_id="versioned-area",
            area_name="Version 1",
            filename="Area_v1.zip",
            filedata=b"data_v1",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Wait to ensure different timestamp (SQLite second precision)
        await asyncio.sleep(1.0)

        # Act - create second version with same areaId
        await area.create_area(
            session=async_session,
            area_id="versioned-area",
            area_name="Version 2",
            filename="Area_v2.zip",
            filedata=b"data_v2",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert - only latest version returned
        areas_list = await area.get_areas(async_session)
        versioned = [a for a in areas_list if a["areaId"] == "versioned-area"]
        assert len(versioned) == 1
        assert versioned[0]["filename"] == "Area_v2.zip"

    async def test_create_area_rejects_deactivated_competent_authority(
        self, async_session: AsyncSession
    ):
        """Test that creating area with a deactivated CA raises InvalidOperationError"""
        # Arrange - create area (creates CA), then manually end the CA
        await area.create_area(
            session=async_session,
            area_id=None,
            area_name=None,
            filename="Area1.zip",
            filedata=b"data1",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        from app.crud import competent_authority as ca_crud

        await ca_crud.mark_as_ended(async_session, "0363")

        # Act & Assert
        with pytest.raises(
            InvalidOperationError,
            match=r"CompetentAuthority '0363' has been deactivated",
        ):
            await area.create_area(
                session=async_session,
                area_id=None,
                area_name=None,
                filename="Area2.zip",
                filedata=b"data2",
                competent_authority_id_str="0363",
                competent_authority_name="Gemeente Amsterdam",
            )

    async def test_create_area_rejects_deactivated_area_id(
        self, async_session: AsyncSession
    ):
        """Test that creating area with a deactivated area_id raises InvalidOperationError"""
        # Arrange - create area, then manually end it
        await area.create_area(
            session=async_session,
            area_id="deactivated-area",
            area_name=None,
            filename="Area1.zip",
            filedata=b"data1",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        from app.crud import area as area_crud

        existing = await area_crud.get_by_area_id(async_session, "deactivated-area")
        assert existing is not None
        await area_crud.mark_as_ended(
            async_session, "deactivated-area", existing.competent_authority_id
        )

        # Act & Assert
        with pytest.raises(
            InvalidOperationError, match=r"Area 'deactivated-area' has been deactivated"
        ):
            await area.create_area(
                session=async_session,
                area_id="deactivated-area",
                area_name=None,
                filename="Area2.zip",
                filedata=b"data2",
                competent_authority_id_str="9999",
                competent_authority_name="New Authority",
            )

    # Tests for delete_area

    async def test_delete_area_success(self, async_session: AsyncSession):
        """Test soft-deleting an area sets ended_at and removes from count"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="delete-me",
            area_name=None,
            filename="DeleteMe.zip",
            filedata=b"data",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        assert await area.count_areas_by_competent_authority(async_session, "0363") == 1

        # Act
        await area.delete_area(async_session, "delete-me", "0363")

        # Assert
        assert await area.count_areas_by_competent_authority(async_session, "0363") == 0

    async def test_delete_area_not_found(self, async_session: AsyncSession):
        """Test deleting non-existent area raises ResourceNotFoundError"""
        with pytest.raises(
            ResourceNotFoundError, match=r"Area 'nonexistent' not found"
        ):
            await area.delete_area(async_session, "nonexistent", "0363")

    async def test_delete_area_already_ended(self, async_session: AsyncSession):
        """Test deleting already-ended area raises ResourceNotFoundError"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="already-ended",
            area_name=None,
            filename="Ended.zip",
            filedata=b"data",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await area.delete_area(async_session, "already-ended", "0363")

        # Act & Assert
        with pytest.raises(
            ResourceNotFoundError, match=r"Area 'already-ended' not found"
        ):
            await area.delete_area(async_session, "already-ended", "0363")

    async def test_delete_area_wrong_ca(self, async_session: AsyncSession):
        """Test deleting area belonging to different CA raises ResourceNotFoundError"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="other-ca-area",
            area_name=None,
            filename="OtherCA.zip",
            filedata=b"data",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Act & Assert - try to delete with wrong CA
        with pytest.raises(
            ResourceNotFoundError, match=r"Area 'other-ca-area' not found"
        ):
            await area.delete_area(async_session, "other-ca-area", "9999")

    async def test_get_areas_by_competent_authority(self, async_session: AsyncSession):
        """Test getting areas scoped to a competent authority"""
        # Arrange - create areas for two different CAs
        await area.create_area(
            session=async_session,
            area_id="ca1-area-1",
            area_name=None,
            filename="CA1_Area1.zip",
            filedata=b"data1",
            competent_authority_id_str="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await area.create_area(
            session=async_session,
            area_id="ca2-area-1",
            area_name=None,
            filename="CA2_Area1.zip",
            filedata=b"data2",
            competent_authority_id_str="0599",
            competent_authority_name="Gemeente Rotterdam",
        )

        # Act
        ca1_areas = await area.get_areas_by_competent_authority(async_session, "0363")
        ca2_areas = await area.get_areas_by_competent_authority(async_session, "0599")

        # Assert
        assert len(ca1_areas) == 1
        assert ca1_areas[0]["areaId"] == "ca1-area-1"
        assert "competentAuthorityId" not in ca1_areas[0]  # Not in own response

        assert len(ca2_areas) == 1
        assert ca2_areas[0]["areaId"] == "ca2-area-1"
