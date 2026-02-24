"""Tests for Activity business service"""

from datetime import datetime

import pytest
from app.exceptions.business import BusinessLogicError, InvalidOperationError
from app.services import activity as activity_service
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import (
    ActivityFactory,
    AreaFactory,
    PlatformFactory,
)


@pytest.mark.database
class TestActivityService:
    """Test suite for Activity business service"""

    # Tests for create_activity

    async def test_create_activity_success(self, async_session: AsyncSession):
        """Test creating a single activity successfully"""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        activity_data = {
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD", "DEU"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Booking Platform",
        }

        # Act
        result = await activity_service.create_activity(async_session, activity_data)

        # Assert
        assert result is not None
        assert result.activity_id is not None
        assert result.registration_number == "REG001"
        count = await activity_service.count_activity(async_session)
        assert count == 1

    async def test_create_activity_auto_generates_id(self, async_session: AsyncSession):
        """Test that activity_id is auto-generated when not provided"""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        await async_session.refresh(area, ["competent_authority"])

        activity_data = {
            "activity_id": None,
            "activity_name": None,
            "url": "http://example.com/listing-auto-id",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG002",
            "area_id": area.area_id,
            "number_of_guests": 2,
            "country_of_guests": ["NLD"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Booking Platform",
        }

        # Act
        result = await activity_service.create_activity(async_session, activity_data)

        # Assert
        assert result.activity_id is not None
        assert len(result.activity_id) == 36  # UUID format

    async def test_create_activity_with_provided_id(self, async_session: AsyncSession):
        """Test creating activity with a provided activity_id"""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        activity_data = {
            "activity_id": "550e8400-e29b-41d4-a716-446655440123",
            "activity_name": "Custom Activity Name",
            "url": "http://example.com/listing-with-id",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD", "DEU"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Booking Platform",
        }

        # Act
        result = await activity_service.create_activity(async_session, activity_data)

        # Assert
        assert result.activity_id == "550e8400-e29b-41d4-a716-446655440123"
        assert result.activity_name == "Custom Activity Name"

    async def test_create_activity_creates_platform(self, async_session: AsyncSession):
        """Test that platform is created if it doesn't exist"""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        await async_session.refresh(area, ["competent_authority"])

        activity_data = {
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD", "DEU"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "new_platform",
            "platform_name": "New Platform",
        }

        # Act
        result = await activity_service.create_activity(async_session, activity_data)

        # Assert
        assert result is not None
        from app.crud import platform as platform_crud

        platform = await platform_crud.get_by_platform_id(async_session, "new_platform")
        assert platform is not None
        assert platform.platform_name == "New Platform"

    async def test_create_activity_versions_existing_platform(
        self, async_session: AsyncSession
    ):
        """Test that existing platform is versioned (old ended, new created)"""
        import asyncio

        # Arrange
        area = await AreaFactory.create_async(async_session)
        await async_session.refresh(area, ["competent_authority"])

        _existing_platform = await PlatformFactory.create_async(
            async_session,
            platform_id="existing_platform",
            platform_name="Existing Platform",
        )

        # Wait to ensure different timestamp (SQLite second precision)
        await asyncio.sleep(1.0)

        activity_data = {
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD", "DEU"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "existing_platform",
            "platform_name": "Existing Platform",
        }

        # Act
        result = await activity_service.create_activity(async_session, activity_data)

        # Assert
        assert result is not None
        from app.models.platform import Platform
        from sqlalchemy import select

        platforms = await async_session.execute(select(Platform))
        all_platforms = platforms.scalars().all()
        assert len(all_platforms) == 2  # Two versions (old ended, new current)

        current_platforms = [p for p in all_platforms if p.ended_at is None]
        assert len(current_platforms) == 1

    async def test_create_activity_nonexistent_area_raises_error(
        self, async_session: AsyncSession
    ):
        """Test that creating activity fails when area doesn't exist"""
        # Arrange
        activity_data = {
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": "00000000-0000-0000-0000-000000000000",
            "number_of_guests": 4,
            "country_of_guests": ["NLD", "DEU"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Booking Platform",
        }

        # Act & Assert
        with pytest.raises(BusinessLogicError, match=r"Area with areaId.*not found"):
            await activity_service.create_activity(async_session, activity_data)

    async def test_create_activity_with_optional_fields(
        self, async_session: AsyncSession
    ):
        """Test creating activity with optional address fields"""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        activity_data = {
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": "A",
            "address_addition": "2h",
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD", "DEU"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Booking Platform",
        }

        # Act
        result = await activity_service.create_activity(async_session, activity_data)

        # Assert
        assert result is not None
        count = await activity_service.count_activity(async_session)
        assert count == 1

    # Tests for count_activity

    async def test_count_activity_empty(self, async_session: AsyncSession):
        """Test counting activities when database is empty"""
        result = await activity_service.count_activity(async_session)
        assert result == 0

    async def test_count_activity_single(self, async_session: AsyncSession):
        """Test counting activities with single record"""
        await ActivityFactory.create_async(async_session)
        result = await activity_service.count_activity(async_session)
        assert result == 1

    async def test_count_activity_multiple(self, async_session: AsyncSession):
        """Test counting activities with multiple records"""
        await ActivityFactory.create_async(async_session)
        await ActivityFactory.create_async(async_session)
        await ActivityFactory.create_async(async_session)
        result = await activity_service.count_activity(async_session)
        assert result == 3

    # Tests for count_activity_by_competent_authority

    async def test_count_activity_by_competent_authority_empty(
        self, async_session: AsyncSession
    ):
        """Test counting activities by competent authority when database is empty"""
        result = await activity_service.count_activity_by_competent_authority(
            async_session, "0363"
        )
        assert result == 0

    async def test_count_activity_by_competent_authority_no_match(
        self, async_session: AsyncSession
    ):
        """Test counting activities by competent authority with no matching records"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await ActivityFactory.create_async(async_session, area_id=area.id)
        result = await activity_service.count_activity_by_competent_authority(
            async_session, "0599"
        )
        assert result == 0

    async def test_count_activity_by_competent_authority_single_match(
        self, async_session: AsyncSession
    ):
        """Test counting activities by competent authority with single match"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await ActivityFactory.create_async(async_session, area_id=area.id)
        result = await activity_service.count_activity_by_competent_authority(
            async_session, "0363"
        )
        assert result == 1

    async def test_count_activity_by_competent_authority_multiple_matches(
        self, async_session: AsyncSession
    ):
        """Test counting activities by competent authority with multiple matches"""
        area1 = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        area2 = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await ActivityFactory.create_async(async_session, area_id=area1.id)
        await ActivityFactory.create_async(async_session, area_id=area1.id)
        await ActivityFactory.create_async(async_session, area_id=area2.id)
        result = await activity_service.count_activity_by_competent_authority(
            async_session, "0363"
        )
        assert result == 3

    async def test_count_activity_by_competent_authority_filters_correctly(
        self, async_session: AsyncSession
    ):
        """Test that counting filters by competent authority correctly"""
        area1 = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        area2 = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0599",
            competent_authority_name="Gemeente Rotterdam",
        )
        await ActivityFactory.create_async(async_session, area_id=area1.id)
        await ActivityFactory.create_async(async_session, area_id=area1.id)
        await ActivityFactory.create_async(async_session, area_id=area2.id)
        result1 = await activity_service.count_activity_by_competent_authority(
            async_session, "0363"
        )
        result2 = await activity_service.count_activity_by_competent_authority(
            async_session, "0599"
        )
        assert result1 == 2
        assert result2 == 1

    # Tests for get_activity_list

    async def test_get_activity_list_empty(self, async_session: AsyncSession):
        """Test getting activities list when database is empty"""
        result = await activity_service.get_activity_list(async_session, "0363")
        assert result == []

    async def test_get_activity_list_no_match(self, async_session: AsyncSession):
        """Test getting activities list with no matching records"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        await ActivityFactory.create_async(async_session, area_id=area.id)
        result = await activity_service.get_activity_list(async_session, "0599")
        assert result == []

    async def test_get_activity_list_single_record(self, async_session: AsyncSession):
        """Test getting activities list with single record"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(
            async_session,
            platform_id="platform01",
            platform_name="Test Platform",
        )
        _activity = await ActivityFactory.create_async(
            async_session,
            url="http://example.com/listing-1",
            area_id=area.id,
            platform_id=platform.id,
        )
        result = await activity_service.get_activity_list(async_session, "0363")
        assert len(result) == 1
        assert result[0]["url"] == "http://example.com/listing-1"
        assert result[0]["platform_id"] == "platform01"
        assert result[0]["platform_name"] == "Test Platform"

    async def test_get_activity_list_response_structure(
        self, async_session: AsyncSession
    ):
        """Test that response structure matches specification"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session, area_id=area.id, platform_id=platform.id
        )
        result = await activity_service.get_activity_list(async_session, "0363")
        assert len(result) == 1
        activity_dict = result[0]

        required_keys = {
            "activity_id",
            "activity_name",
            "platform_id",
            "platform_name",
            "url",
            "address_street",
            "address_number",
            "address_letter",
            "address_addition",
            "address_postal_code",
            "address_city",
            "registration_number",
            "area_id",
            "number_of_guests",
            "country_of_guests",
            "temporal_start_date_time",
            "temporal_end_date_time",
            "created_at",
        }
        assert set(activity_dict.keys()) == required_keys

    async def test_get_activity_list_multiple_records(
        self, async_session: AsyncSession
    ):
        """Test getting activities list with multiple records"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session, area_id=area.id, platform_id=platform.id
        )
        await ActivityFactory.create_async(
            async_session, area_id=area.id, platform_id=platform.id
        )
        await ActivityFactory.create_async(
            async_session, area_id=area.id, platform_id=platform.id
        )
        result = await activity_service.get_activity_list(async_session, "0363")
        assert len(result) == 3

    async def test_get_activity_list_filters_by_competent_authority(
        self, async_session: AsyncSession
    ):
        """Test that listing filters by competent authority correctly"""
        area1 = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        area2 = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0599",
            competent_authority_name="Gemeente Rotterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session, area_id=area1.id, platform_id=platform.id
        )
        await ActivityFactory.create_async(
            async_session, area_id=area1.id, platform_id=platform.id
        )
        await ActivityFactory.create_async(
            async_session, area_id=area2.id, platform_id=platform.id
        )
        result1 = await activity_service.get_activity_list(async_session, "0363")
        result2 = await activity_service.get_activity_list(async_session, "0599")
        assert len(result1) == 2
        assert len(result2) == 1

    async def test_get_activity_list_with_pagination_offset(
        self, async_session: AsyncSession
    ):
        """Test getting activities list with offset pagination"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        for _ in range(4):
            await ActivityFactory.create_async(
                async_session, area_id=area.id, platform_id=platform.id
            )
        result = await activity_service.get_activity_list(
            async_session, "0363", offset=2
        )
        assert len(result) == 2

    async def test_get_activity_list_with_pagination_limit(
        self, async_session: AsyncSession
    ):
        """Test getting activities list with limit pagination"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        for _ in range(3):
            await ActivityFactory.create_async(
                async_session, area_id=area.id, platform_id=platform.id
            )
        result = await activity_service.get_activity_list(
            async_session, "0363", limit=2
        )
        assert len(result) == 2

    async def test_get_activity_list_with_pagination_offset_and_limit(
        self, async_session: AsyncSession
    ):
        """Test getting activities list with both offset and limit pagination"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        for _ in range(5):
            await ActivityFactory.create_async(
                async_session, area_id=area.id, platform_id=platform.id
            )
        result = await activity_service.get_activity_list(
            async_session, "0363", offset=1, limit=2
        )
        assert len(result) == 2

    async def test_get_activity_list_pagination_offset_beyond_results(
        self, async_session: AsyncSession
    ):
        """Test pagination with offset beyond available results"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session, area_id=area.id, platform_id=platform.id
        )
        await ActivityFactory.create_async(
            async_session, area_id=area.id, platform_id=platform.id
        )
        result = await activity_service.get_activity_list(
            async_session, "0363", offset=10
        )
        assert len(result) == 0

    async def test_get_activity_list_includes_platform_info(
        self, async_session: AsyncSession
    ):
        """Test that activities list includes platform information via relationship"""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(
            async_session,
            platform_id="platform99",
            platform_name="Super Platform",
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/test",
            area_id=area.id,
            platform_id=platform.id,
        )
        result = await activity_service.get_activity_list(async_session, "0363")
        assert len(result) == 1
        assert result[0]["platform_id"] == "platform99"
        assert result[0]["platform_name"] == "Super Platform"

    async def test_create_activity_versioning_marks_previous_as_ended(
        self, async_session: AsyncSession
    ):
        """Test creating activity with same activityId marks previous version as ended"""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        activity_data_v1 = {
            "activity_id": "versioned-activity",
            "activity_name": "Version 1",
            "url": "http://example.com/listing-v1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Test Platform",
        }

        await activity_service.create_activity(async_session, activity_data_v1)

        # Wait to ensure different timestamp (SQLite second precision)
        import asyncio

        await asyncio.sleep(1.0)

        # Act - create second version with same activityId
        activity_data_v2 = {
            **activity_data_v1,
            "activity_name": "Version 2",
            "url": "http://example.com/listing-v2",
        }
        await activity_service.create_activity(async_session, activity_data_v2)

        # Assert - only latest version returned
        result = await activity_service.get_activity_list(async_session, "0363")
        versioned = [a for a in result if a["activity_id"] == "versioned-activity"]
        assert len(versioned) == 1
        assert versioned[0]["url"] == "http://example.com/listing-v2"

    async def test_create_activity_rejects_deactivated_platform(
        self, async_session: AsyncSession
    ):
        """Test that creating activity with a deactivated platform raises InvalidOperationError"""
        # Arrange - create activity (creates platform), then manually end the platform
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        activity_data = {
            "activity_id": None,
            "activity_name": None,
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "deactivated-platform",
            "platform_name": "Test Platform",
        }
        await activity_service.create_activity(async_session, activity_data)

        from app.crud import platform as platform_crud

        await platform_crud.mark_as_ended(async_session, "deactivated-platform")

        # Act & Assert
        with pytest.raises(
            InvalidOperationError,
            match=r"Platform 'deactivated-platform' has been deactivated",
        ):
            await activity_service.create_activity(async_session, {**activity_data})

    async def test_create_activity_rejects_deactivated_activity_id(
        self, async_session: AsyncSession
    ):
        """Test that creating activity with a deactivated activity_id raises InvalidOperationError"""
        # Arrange - create activity, then manually end it
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        activity_data = {
            "activity_id": "deactivated-activity",
            "activity_name": None,
            "url": "http://example.com/listing-1",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 4,
            "country_of_guests": ["NLD"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Test Platform",
        }
        await activity_service.create_activity(async_session, activity_data)

        from app.crud import activity as activity_crud

        existing = await activity_crud.get_by_activity_id(
            async_session, "deactivated-activity"
        )
        assert existing is not None
        await activity_crud.mark_as_ended(
            async_session, "deactivated-activity", existing.platform_id
        )

        # Act & Assert - use a different platform to avoid the platform guard
        with pytest.raises(
            InvalidOperationError,
            match=r"Activity 'deactivated-activity' has been deactivated",
        ):
            await activity_service.create_activity(
                async_session,
                {
                    **activity_data,
                    "platform_id_str": "platform02",
                    "platform_name": "Other",
                },
            )

    async def test_get_activities_by_platform(self, async_session: AsyncSession):
        """Test getting activities scoped to a platform"""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )

        # Create activity for platform01
        activity_data_p1 = {
            "activity_id": "p1-activity",
            "activity_name": None,
            "url": "http://example.com/p1-listing",
            "address_street": "Damstraat",
            "address_number": "1",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1012JS",
            "address_city": "Amsterdam",
            "registration_number": "REG001",
            "area_id": area.area_id,
            "number_of_guests": 2,
            "country_of_guests": ["NLD"],
            "temporal_start_date_time": datetime(2025, 6, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 6, 8, 12, 0, 0),
            "platform_id_str": "platform01",
            "platform_name": "Platform One",
        }
        await activity_service.create_activity(async_session, activity_data_p1)

        # Create activity for platform02
        activity_data_p2 = {
            "activity_id": "p2-activity",
            "activity_name": None,
            "url": "http://example.com/p2-listing",
            "address_street": "Keizersgracht",
            "address_number": "5",
            "address_letter": None,
            "address_addition": None,
            "address_postal_code": "1015AA",
            "address_city": "Amsterdam",
            "registration_number": "REG002",
            "area_id": area.area_id,
            "number_of_guests": 3,
            "country_of_guests": ["DEU"],
            "temporal_start_date_time": datetime(2025, 7, 1, 12, 0, 0),
            "temporal_end_date_time": datetime(2025, 7, 8, 12, 0, 0),
            "platform_id_str": "platform02",
            "platform_name": "Platform Two",
        }
        await activity_service.create_activity(async_session, activity_data_p2)

        # Act
        p1_activities = await activity_service.get_activities_by_platform(
            async_session, "platform01"
        )
        p2_activities = await activity_service.get_activities_by_platform(
            async_session, "platform02"
        )

        # Assert
        assert len(p1_activities) == 1
        assert p1_activities[0]["activity_id"] == "p1-activity"
        assert p1_activities[0]["competent_authority_id"] == "0363"
        assert p1_activities[0]["competent_authority_name"] == "Gemeente Amsterdam"
        assert "platform_id" not in p1_activities[0]  # Not in own response

        assert len(p2_activities) == 1
        assert p2_activities[0]["activity_id"] == "p2-activity"
