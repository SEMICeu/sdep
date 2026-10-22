"""Tests for Area business service"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from app.crud import competent_authority as ca_crud
from app.enums import Regulation
from app.exceptions.business import (
    DuplicateResourceError,
    InvalidOperationError,
    ResourceNotFoundError,
)
from app.models.area import Area
from app.services import area
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory
from tests.services.test_platform import hide_first_lookup


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
        assert result[0].competent_authority.competent_authority_id == "0363"
        assert (
            result[0].competent_authority.competent_authority_name
            == "Gemeente Amsterdam"
        )
        assert result[0].area_id is not None
        assert result[0].filename is not None
        assert result[0].created_at is not None

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
        area1 = next(
            (
                a
                for a in result
                if a.competent_authority.competent_authority_id == "0363"
            ),
            None,
        )
        area2 = next(
            (
                a
                for a in result
                if a.competent_authority.competent_authority_id == "0599"
            ),
            None,
        )
        area3 = next(
            (
                a
                for a in result
                if a.competent_authority.competent_authority_id == "0518"
            ),
            None,
        )

        assert area1 is not None
        assert (
            area1.competent_authority.competent_authority_name == "Gemeente Amsterdam"
        )

        assert area2 is not None
        assert (
            area2.competent_authority.competent_authority_name == "Gemeente Rotterdam"
        )

        assert area3 is not None
        assert area3.competent_authority.competent_authority_name == "Gemeente Den Haag"

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
        for area_obj in result:
            assert area_obj.competent_authority.competent_authority_id == "0363"
            assert (
                area_obj.competent_authority.competent_authority_name
                == "Gemeente Amsterdam"
            )

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
        area_obj = result[0]

        assert hasattr(area_obj, "area_id")
        assert hasattr(area_obj, "area_name")
        assert hasattr(area_obj, "competent_authority")
        assert hasattr(area_obj, "filename")
        assert hasattr(area_obj, "created_at")

        assert isinstance(area_obj.area_id, str)
        assert len(area_obj.area_id) == 36  # UUID format
        assert isinstance(area_obj.area_name, str) or area_obj.area_name is None
        assert isinstance(area_obj.competent_authority.competent_authority_id, str)
        assert isinstance(area_obj.competent_authority.competent_authority_name, str)
        assert isinstance(area_obj.filename, str)

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

        # Assert: verify pagination returns correct count and valid IDs.
        # We don't assert specific IDs because all areas are created with
        # near-identical timestamps, making order_by(created_at.desc()) non-deterministic.
        assert len(result) == 2
        all_ids = {"0001", "0002", "0003", "0004"}
        ids = {area.competent_authority.competent_authority_id for area in result}
        assert ids.issubset(all_ids)

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
        ids = {area.competent_authority.competent_authority_id for area in result}
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

    async def test_get_area_by_id_returns_none_when_missing(
        self, async_session: AsyncSession
    ):
        assert await area.get_area_by_id(async_session, "missing-area") is None

    async def test_get_area_by_id_returns_file_payload(
        self, async_session: AsyncSession
    ):
        created = await AreaFactory.create_async(
            async_session,
            area_id="service-area-1",
            filename="service.zip",
            filedata=b"payload",
        )

        result = await area.get_area_by_id(async_session, created.area_id)

        assert result is not None
        assert result.filename == "service.zip"
        assert result.filedata == b"payload"

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
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert
        assert area_obj.area_id == "test-area-001"
        assert area_obj.area_name == "Test Area"
        assert area_obj.filename == "TestArea.zip"
        assert area_obj.filedata == b"data1"

        count = await area.count_areas(async_session)
        assert count == 1

    async def test_create_area_regulation_defaults_to_all(
        self, async_session: AsyncSession
    ):
        """Test that regulation defaults to 'all' when not supplied."""
        area_obj = await area.create_area(
            session=async_session,
            area_id="test-area-reg-default",
            area_name=None,
            filename="area.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        assert area_obj.regulation == Regulation.all

    async def test_create_area_regulation_listing(self, async_session: AsyncSession):
        """Test creating an area with regulation=listing."""
        area_obj = await area.create_area(
            session=async_session,
            area_id="test-area-reg-listing",
            area_name=None,
            filename="area.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
            regulation=Regulation.listing,
        )
        assert area_obj.regulation == Regulation.listing

    async def test_create_area_regulation_activity(self, async_session: AsyncSession):
        """Test creating an area with regulation=activity."""
        area_obj = await area.create_area(
            session=async_session,
            area_id="test-area-reg-activity",
            area_name=None,
            filename="area.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
            regulation=Regulation.activity,
        )
        assert area_obj.regulation == Regulation.activity

    async def test_create_area_regulation_all_explicit(
        self, async_session: AsyncSession
    ):
        """Test creating an area with regulation=all explicitly."""
        area_obj = await area.create_area(
            session=async_session,
            area_id="test-area-reg-all",
            area_name=None,
            filename="area.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
            regulation=Regulation.all,
        )
        assert area_obj.regulation == Regulation.all

    async def test_create_area_auto_generates_id(self, async_session: AsyncSession):
        """Test that area_id is auto-generated when None"""
        # Act
        area_obj = await area.create_area(
            session=async_session,
            area_id=None,
            area_name=None,
            filename="AutoId.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert
        assert area_obj.area_id is not None
        assert len(area_obj.area_id) == 36  # UUID format

    async def test_generated_area_id_makes_a_resend_a_retry(
        self, async_session: AsyncSession
    ):
        """Same upload → same area; after a delete the same upload is a new area."""

        async def upload(filedata: bytes = b"data"):
            return await area.create_area(
                session=async_session,
                area_id=None,
                area_name="Centrum",
                filename="Centrum.zip",
                filedata=filedata,
                client_id="0363",
                competent_authority_name="Gemeente Amsterdam",
            )

        first = await upload()
        resent = await upload()
        assert uuid.UUID(first.area_id).version == 8
        assert resent.area_id == first.area_id
        assert resent.created_at == first.created_at
        assert resent.competent_authority.competent_authority_name == (
            "Gemeente Amsterdam"
        )
        assert (await upload(b"other data")).area_id != first.area_id
        assert await area.count_areas_by_client_id(async_session, "0363") == 2

        await area.delete_area_by_client_id(async_session, first.area_id, "0363")
        new = await upload()
        assert new.area_id != first.area_id
        assert (await upload()).area_id == new.area_id
        assert await area.count_areas_by_client_id(async_session, "0363") == 2

    async def test_identical_upload_with_its_area_id_is_a_resend(
        self, async_session: AsyncSession
    ):
        """Same areaId and upload → the stored area; another upload → a new version."""

        async def upload(regulation: Regulation | None = None):
            return await area.create_area(
                session=async_session,
                area_id="own-area",
                area_name="Centrum",
                filename="Centrum.zip",
                filedata=b"data",
                client_id="0363",
                competent_authority_name="Gemeente Amsterdam",
                regulation=regulation,
            )

        first = await upload()
        resent = await upload(Regulation.all)  # the default spelled out
        assert resent.created_at == first.created_at
        await asyncio.sleep(1.0)  # SQLite second precision: another createdAt
        changed = await upload(Regulation.listing)
        assert changed.regulation == Regulation.listing
        assert await area.count_areas_by_client_id(async_session, "0363") == 1
        versions = (
            await async_session.execute(select(Area).where(Area.area_id == "own-area"))
        ).scalars()
        assert len(versions.all()) == 2

    async def test_other_upload_or_ca_gives_another_area(
        self, async_session: AsyncSession
    ):
        """Another areaName, filename, regulation or CA: another generated areaId."""
        base = {
            "area_id": None,
            "area_name": "Centrum",
            "filename": "Centrum.zip",
            "filedata": b"data",
            "client_id": "0363",
            "competent_authority_name": "Gemeente Amsterdam",
        }
        variants = [
            {},
            {"area_name": "West"},
            {"filename": "West.zip"},
            {"regulation": Regulation.activity},
            {"client_id": "0599", "competent_authority_name": "Gemeente Rotterdam"},
        ]
        ids = set()
        for variant in variants:
            created = await area.create_area(
                session=async_session, **{**base, **variant}
            )
            ids.add(created.area_id)
        assert len(ids) == len(variants)

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
            client_id="8888",
            competent_authority_name="Test Authority",
        )

        # Assert
        from app.crud import competent_authority as ca_crud

        ca = await ca_crud.get_by_client_id(async_session, "8888")
        assert ca is not None
        assert ca.client_id == "8888"
        assert ca.competent_authority_id != "8888"
        assert ca.competent_authority_name == "Test Authority"

    async def test_create_area_versions_competent_authority(
        self, async_session: AsyncSession
    ):
        """CA is reused when name unchanged, versioned when JWT-supplied name changes."""
        import asyncio

        from app.models.competent_authority import CompetentAuthority
        from sqlalchemy import select

        # Arrange - create first area (creates CA)
        await area.create_area(
            session=async_session,
            area_id="area-1",
            area_name=None,
            filename="Area1.zip",
            filedata=b"data1",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        await asyncio.sleep(1.0)

        # Act - second area with unchanged CA name → CA must be reused
        await area.create_area(
            session=async_session,
            area_id="area-2",
            area_name=None,
            filename="Area2.zip",
            filedata=b"data2",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        cas = await async_session.execute(select(CompetentAuthority))
        all_cas = cas.scalars().all()
        assert len(all_cas) == 1  # No new CA version when name unchanged
        assert all_cas[0].ended_at is None

        await asyncio.sleep(1.0)

        # Act - third area with changed CA name → CA must be versioned
        await area.create_area(
            session=async_session,
            area_id="area-3",
            area_name=None,
            filename="Area3.zip",
            filedata=b"data3",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam (renamed)",
        )

        cas = await async_session.execute(select(CompetentAuthority))
        all_cas = cas.scalars().all()
        assert len(all_cas) == 2  # Old ended, new current
        current_cas = [ca for ca in all_cas if ca.ended_at is None]
        assert len(current_cas) == 1
        assert current_cas[0].competent_authority_name == "Gemeente Amsterdam (renamed)"

        area_count = await area.count_areas(async_session)
        assert area_count == 3

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
            client_id="0363",
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
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Assert - only latest version returned
        areas_list = await area.get_areas(async_session)
        versioned = [a for a in areas_list if a.area_id == "versioned-area"]
        assert len(versioned) == 1
        assert versioned[0].filename == "Area_v2.zip"

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
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        from app.crud import competent_authority as ca_crud

        await ca_crud.mark_as_ended_by_client_id(async_session, "0363")

        # Act & Assert
        with pytest.raises(
            InvalidOperationError,
            match=r"CompetentAuthority client '0363' has been deactivated",
        ):
            await area.create_area(
                session=async_session,
                area_id=None,
                area_name=None,
                filename="Area2.zip",
                filedata=b"data2",
                client_id="0363",
                competent_authority_name="Gemeente Amsterdam",
            )

    async def test_create_area_rejects_deactivated_area_id(
        self, async_session: AsyncSession
    ):
        """Test that recreating an area with a deactivated area_id for the same CA raises InvalidOperationError"""
        import asyncio

        # Arrange - create area, then manually end it
        await area.create_area(
            session=async_session,
            area_id="deactivated-area",
            area_name=None,
            filename="Area1.zip",
            filedata=b"data1",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        from app.crud import area as area_crud

        existing = await area_crud.get_by_area_id(async_session, "deactivated-area")
        assert existing is not None
        await area_crud.mark_as_ended(
            async_session, "deactivated-area", existing.competent_authority_id
        )

        # Wait to ensure distinct CA version timestamp (SQLite second precision)
        await asyncio.sleep(1.0)

        # Act & Assert - same CA cannot recreate a deactivated area_id
        with pytest.raises(
            InvalidOperationError, match=r"Area 'deactivated-area' has been deactivated"
        ):
            await area.create_area(
                session=async_session,
                area_id="deactivated-area",
                area_name=None,
                filename="Area2.zip",
                filedata=b"data2",
                client_id="0363",
                competent_authority_name="Gemeente Amsterdam",
            )

    async def test_create_area_refuses_area_id_of_another_ca(
        self, async_session: AsyncSession
    ):
        """An areaId has one owner: another CA gets 409 and the owner's area stays."""
        ca1_area = await area.create_area(
            session=async_session,
            area_id="shared-fid",
            area_name="CA1 area",
            filename="CA1.zip",
            filedata=b"ca1-data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        with pytest.raises(
            DuplicateResourceError,
            match=r"areaId 'shared-fid' is already in use by another competent authority",
        ):
            await area.create_area(
                session=async_session,
                area_id="shared-fid",
                area_name="CA2 area",
                filename="CA2.zip",
                filedata=b"ca2-data",
                client_id="0364",
                competent_authority_name="Gemeente Rotterdam",
            )

        # The owner's area is neither ended nor taken over
        current = await area.get_area_by_id(async_session, "shared-fid")
        assert current is not None
        assert current.id == ca1_area.id
        assert current.ended_at is None
        assert await area.get_areas_by_client_id(async_session, "0364") == []

    async def test_create_area_deleted_area_id_stays_with_its_owner(
        self, async_session: AsyncSession
    ):
        """A deleted areaId stays reserved: another CA cannot take it over."""
        await area.create_area(
            session=async_session,
            area_id="shared-fid",
            area_name=None,
            filename="CA1.zip",
            filedata=b"ca1-data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await area.delete_area_by_client_id(async_session, "shared-fid", "0363")

        with pytest.raises(DuplicateResourceError):
            await area.create_area(
                session=async_session,
                area_id="shared-fid",
                area_name=None,
                filename="CA2.zip",
                filedata=b"ca2-data",
                client_id="0364",
                competent_authority_name="Gemeente Rotterdam",
            )

    async def test_create_area_after_ca_rename_versions_the_same_area(
        self, async_session: AsyncSession
    ):
        """A CA rename creates a new CA version; its areaId stays its own."""
        first = await area.create_area(
            session=async_session,
            area_id="rename-fid",
            area_name=None,
            filename="v1.zip",
            filedata=b"v1",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        # Backdate, so the next versions get another created_at (SQLite seconds)
        first.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        first.competent_authority.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        await async_session.flush()

        second = await area.create_area(
            session=async_session,
            area_id="rename-fid",
            area_name=None,
            filename="v2.zip",
            filedata=b"v2",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam (renamed)",
        )

        assert second.competent_authority_id != first.competent_authority_id
        current = await area.get_area_by_id(async_session, "rename-fid")
        assert current is not None
        assert current.id == second.id

    async def test_delete_area_success(self, async_session: AsyncSession):
        """Test soft-deleting an area sets ended_at and removes from count"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="delete-me",
            area_name=None,
            filename="DeleteMe.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        assert await area.count_areas_by_client_id(async_session, "0363") == 1

        # Act
        await area.delete_area_by_client_id(async_session, "delete-me", "0363")

        # Assert
        assert await area.count_areas_by_client_id(async_session, "0363") == 0

    async def test_delete_area_not_found(self, async_session: AsyncSession):
        """Test deleting non-existent area raises ResourceNotFoundError"""
        with pytest.raises(
            ResourceNotFoundError, match=r"Area 'nonexistent' not found"
        ):
            await area.delete_area_by_client_id(async_session, "nonexistent", "0363")

    async def test_delete_area_already_ended(self, async_session: AsyncSession):
        """Test deleting already-ended area raises ResourceNotFoundError"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="already-ended",
            area_name=None,
            filename="Ended.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await area.delete_area_by_client_id(async_session, "already-ended", "0363")

        # Act & Assert
        with pytest.raises(
            ResourceNotFoundError, match=r"Area 'already-ended' not found"
        ):
            await area.delete_area_by_client_id(async_session, "already-ended", "0363")

    async def test_delete_area_wrong_ca(self, async_session: AsyncSession):
        """Test deleting area belonging to different CA raises ResourceNotFoundError"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="other-ca-area",
            area_name=None,
            filename="OtherCA.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Act & Assert - try to delete with wrong CA
        with pytest.raises(
            ResourceNotFoundError, match=r"Area 'other-ca-area' not found"
        ):
            await area.delete_area_by_client_id(async_session, "other-ca-area", "9999")

    async def test_get_areas_by_client_id(self, async_session: AsyncSession):
        """Test getting areas scoped to a competent authority"""
        # Arrange - create areas for two different CAs
        await area.create_area(
            session=async_session,
            area_id="ca1-area-1",
            area_name=None,
            filename="CA1_Area1.zip",
            filedata=b"data1",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await area.create_area(
            session=async_session,
            area_id="ca2-area-1",
            area_name=None,
            filename="CA2_Area1.zip",
            filedata=b"data2",
            client_id="0599",
            competent_authority_name="Gemeente Rotterdam",
        )

        # Act
        ca1_areas = await area.get_areas_by_client_id(async_session, "0363")
        ca2_areas = await area.get_areas_by_client_id(async_session, "0599")

        # Assert
        assert len(ca1_areas) == 1
        assert ca1_areas[0].area_id == "ca1-area-1"
        assert ca1_areas[0].competent_authority.client_id == "0363"
        assert ca1_areas[0].competent_authority.competent_authority_id != "0363"

        assert len(ca2_areas) == 1
        assert ca2_areas[0].area_id == "ca2-area-1"

    # Tests for get_area_by_area_id_and_client_id

    async def test_get_area_by_area_id_and_client_id_success(
        self, async_session: AsyncSession
    ):
        """Test get_area_by_area_id_and_client_id returns filename and filedata for matching CA"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="own-area",
            area_name=None,
            filename="OwnArea.zip",
            filedata=b"shapefiledata",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Act
        result = await area.get_area_by_area_id_and_client_id(
            async_session, "own-area", "0363"
        )

        # Assert
        assert result is not None
        assert result.filename == "OwnArea.zip"
        assert result.filedata == b"shapefiledata"

    async def test_get_area_by_area_id_and_client_id_not_found(
        self, async_session: AsyncSession
    ):
        """Test get_area_by_area_id_and_client_id returns None for non-existent area"""
        result = await area.get_area_by_area_id_and_client_id(
            async_session, "does-not-exist", "0363"
        )

        assert result is None

    async def test_get_area_by_area_id_and_client_id_wrong_ca(
        self, async_session: AsyncSession
    ):
        """Test get_area_by_area_id_and_client_id returns None for area belonging to a different CA"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="ca1-area",
            area_name=None,
            filename="CA1Area.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Act - different CA tries to access
        result = await area.get_area_by_area_id_and_client_id(
            async_session, "ca1-area", "9999"
        )

        # Assert
        assert result is None

    async def test_get_area_by_area_id_and_client_id_deleted_area(
        self, async_session: AsyncSession
    ):
        """Test get_area_by_area_id_and_client_id returns None for soft-deleted area"""
        # Arrange
        await area.create_area(
            session=async_session,
            area_id="deleted-area",
            area_name=None,
            filename="Deleted.zip",
            filedata=b"data",
            client_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await area.delete_area_by_client_id(async_session, "deleted-area", "0363")

        # Act
        result = await area.get_area_by_area_id_and_client_id(
            async_session, "deleted-area", "0363"
        )

        # Assert
        assert result is None


@pytest.mark.database
class TestParallelFirstUpload:
    """A first upload that loses the CA claim reuses the CA of the winner."""

    def _upload(self, session: AsyncSession, area_id: str):
        return area.create_area(
            session=session,
            area_id=area_id,
            area_name=None,
            filename=f"{area_id}.zip",
            filedata=area_id.encode(),
            client_id="ca-race",
            competent_authority_name="Race CA",
        )

    async def test_loser_reuses_the_winner(
        self, async_session: AsyncSession, monkeypatch
    ):
        winner = await self._upload(async_session, "race-1")
        hide_first_lookup(monkeypatch, ca_crud)

        loser = await self._upload(async_session, "race-2")

        assert loser.competent_authority.id == winner.competent_authority.id

    async def test_refuses_when_no_winner_is_found(
        self, async_session: AsyncSession, monkeypatch
    ):
        await self._upload(async_session, "race-3")

        async def missing(session, client_id):
            return None

        hide_first_lookup(monkeypatch, ca_crud)
        monkeypatch.setattr(ca_crud, "get_by_client_id", missing)
        with pytest.raises(DuplicateResourceError):
            await self._upload(async_session, "race-4")
