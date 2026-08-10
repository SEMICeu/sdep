"""Tests for Activity CRUD operations."""

from datetime import datetime

import pytest
from app.crud import activity
from app.enums import ActivityStatus
from app.schemas.activity import ActivityBulkCreate
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import ActivityFactory, AreaFactory, PlatformFactory


@pytest.mark.database
class TestActivityCRUD:
    """Test suite for Activity CRUD operations."""

    async def test_create_activity(self, async_session: AsyncSession):
        """Test creating a new activity."""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)
        activity_id = "550e8400-e29b-41d4-a716-446655440000"
        activity_name = "Amsterdam Summer Rental 2025"
        url = "http://example.com/listing-1"
        address_thoroughfare = "Main Street"
        address_locator_designator_number = 123
        address_post_code = "1234AB"
        address_post_name = "Amsterdam"
        address_full_address = "Main Street 123, 1234AB Amsterdam"
        registration_number = "REG123456"
        number_of_guests = 4
        country_of_guests = ["NLD", "DEU"]
        temporal_start = datetime(2025, 6, 1, 12, 0, 0)
        temporal_end = datetime(2025, 6, 8, 12, 0, 0)

        # Act
        result = await activity.create(
            session=async_session,
            activity_id=activity_id,
            activity_name=activity_name,
            platform_id=platform.id,
            area_id=area.id,
            url=url,
            address_thoroughfare=address_thoroughfare,
            address_locator_designator_number=address_locator_designator_number,
            address_locator_designator_letter=None,
            address_locator_designator_addition=None,
            address_post_code=address_post_code,
            address_post_name=address_post_name,
            address_full_address=address_full_address,
            registration_number=registration_number,
            number_of_guests=number_of_guests,
            country_of_guests=country_of_guests,
            temporal_start_date_time=temporal_start,
            temporal_end_date_time=temporal_end,
        )

        # Assert
        assert result.id is not None
        assert isinstance(result.id, int)
        assert result.activity_id == activity_id
        assert result.activity_name == activity_name
        assert result.status == ActivityStatus.finished
        assert result.url == url
        assert result.address_thoroughfare == address_thoroughfare
        assert (
            result.address_locator_designator_number
            == address_locator_designator_number
        )
        assert result.address_locator_designator_letter is None
        assert result.address_locator_designator_addition is None
        assert result.address_post_code == address_post_code
        assert result.address_post_name == address_post_name
        assert result.address_full_address == address_full_address
        assert result.registration_number == registration_number
        assert result.area_id == area.id
        assert result.number_of_guests == number_of_guests
        assert result.country_of_guests == country_of_guests
        assert result.temporal_start_date_time == temporal_start
        assert result.temporal_end_date_time == temporal_end
        assert result.platform_id == platform.id
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_activity_with_auto_generated_id(
        self, async_session: AsyncSession
    ):
        """Test creating activity with auto-generated activity_id (UUID)."""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)

        # Act
        result = await activity.create(
            session=async_session,
            activity_id=None,
            activity_name=None,
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/listing-autogen",
            address_thoroughfare="Auto Street",
            address_locator_designator_number=999,
            address_locator_designator_letter=None,
            address_locator_designator_addition=None,
            address_post_code="9999ZZ",
            address_post_name="AutoCity",
            address_full_address="Auto Street 999, 9999ZZ AutoCity",
            registration_number="REGAUTO",
            number_of_guests=2,
            country_of_guests=["NLD"],
            temporal_start_date_time=datetime(2025, 6, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 6, 8, 12, 0, 0),
        )

        # Assert
        assert result.activity_id is not None  # Should be auto-generated UUID
        assert len(result.activity_id) == 36  # UUID format
        assert result.activity_name is None  # Should be None when not provided
        assert result.status == ActivityStatus.finished

    async def test_create_activity_with_explicit_cancelled_status(
        self, async_session: AsyncSession
    ):
        """Test creating activity with explicit cancelled lifecycle status."""
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)

        result = await activity.create(
            session=async_session,
            activity_id="cancelled-activity-id",
            activity_name="Cancelled stay",
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/listing-cancelled",
            address_thoroughfare="Cancel Street",
            address_locator_designator_number=10,
            address_locator_designator_letter=None,
            address_locator_designator_addition=None,
            address_post_code="1234AB",
            address_post_name="Amsterdam",
            address_full_address="Cancel Street 10, 1234AB Amsterdam",
            registration_number="REGCANCELLED",
            number_of_guests=1,
            country_of_guests=["NLD"],
            temporal_start_date_time=datetime(2025, 6, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 6, 8, 12, 0, 0),
            status=ActivityStatus.cancelled,
        )

        assert result.status == ActivityStatus.cancelled

    async def test_create_activity_without_locator_designator_number(
        self, async_session: AsyncSession
    ):
        """Test creating activity with None locator_designator_number (now optional)."""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)

        # Act
        result = await activity.create(
            session=async_session,
            activity_id=None,
            activity_name=None,
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/listing-no-number",
            address_thoroughfare="Nameless Street",
            address_locator_designator_number=None,
            address_locator_designator_letter=None,
            address_locator_designator_addition=None,
            address_post_code="1234AB",
            address_post_name="Amsterdam",
            address_full_address="Nameless Street, 1234AB Amsterdam",
            registration_number="REGNONUMBER",
            number_of_guests=1,
            country_of_guests=["N/A"],
            temporal_start_date_time=datetime(2025, 6, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 6, 8, 12, 0, 0),
        )

        # Assert
        assert result.id is not None
        assert result.address_locator_designator_number is None

    async def test_create_activity_with_optional_fields(
        self, async_session: AsyncSession
    ):
        """Test creating activity with optional address fields."""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)
        address_locator_designator_letter = "A"
        address_locator_designator_addition = "1hoog"

        # Act
        result = await activity.create(
            session=async_session,
            activity_id="7c9e6679-7425-40de-944b-e07fc1f90ae7",
            activity_name="Rotterdam Rental",
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/listing-2",
            address_thoroughfare="Side Street",
            address_locator_designator_number=456,
            address_locator_designator_letter=address_locator_designator_letter,
            address_locator_designator_addition=address_locator_designator_addition,
            address_post_code="5678CD",
            address_post_name="Rotterdam",
            address_full_address="Side Street 456A-1hoog, 5678CD Rotterdam",
            registration_number="REG789012",
            number_of_guests=2,
            country_of_guests=["BEL"],
            temporal_start_date_time=datetime(2025, 7, 1, 14, 0, 0),
            temporal_end_date_time=datetime(2025, 7, 5, 14, 0, 0),
        )

        # Assert
        assert (
            result.address_locator_designator_letter
            == address_locator_designator_letter
        )
        assert (
            result.address_locator_designator_addition
            == address_locator_designator_addition
        )

    async def test_exists_activity(self, async_session: AsyncSession):
        """Test checking if activity exists."""
        # Arrange
        act = await ActivityFactory.create_async(async_session)

        # Act
        exists = await activity.exists(async_session, act.id)
        not_exists = await activity.exists(async_session, 99999)

        # Assert
        assert exists is True
        assert not_exists is False

    async def test_count_activity(self, async_session: AsyncSession):
        """Test counting activities."""
        # Arrange
        await ActivityFactory.create_async(async_session)
        await ActivityFactory.create_async(async_session)
        await ActivityFactory.create_async(async_session)

        # Act
        total = await activity.count(async_session)

        # Assert
        assert total == 3

    async def test_get_all_activity(self, async_session: AsyncSession):
        """Test getting all activities."""
        # Arrange
        await ActivityFactory.create_async(async_session)
        await ActivityFactory.create_async(async_session)

        # Act
        results = await activity.get_all(async_session)

        # Assert
        assert len(results) == 2

    async def test_get_all_activity_with_pagination(self, async_session: AsyncSession):
        """Test getting activities with pagination."""
        # Arrange
        for _ in range(5):
            await ActivityFactory.create_async(async_session)

        # Act
        page1 = await activity.get_all(async_session, offset=0, limit=2)
        page2 = await activity.get_all(async_session, offset=2, limit=2)
        page3 = await activity.get_all(async_session, offset=4, limit=2)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

    async def test_get_by_id(self, async_session: AsyncSession):
        """Test getting activity by id."""
        # Arrange
        act = await ActivityFactory.create_async(async_session)

        # Act
        result = await activity.get_by_id(async_session, act.id)

        # Assert
        assert result is not None
        assert result.id == act.id
        assert result.url == act.url

    async def test_get_by_id_not_found(self, async_session: AsyncSession):
        """Test getting a non-existent activity by id."""
        # Act
        result = await activity.get_by_id(async_session, 99999)

        # Assert
        assert result is None

    async def test_get_by_url(self, async_session: AsyncSession):
        """Test getting activities by url."""
        # Arrange
        test_url = "http://example.com/special-listing"
        act = await ActivityFactory.create_async(async_session, url=test_url)

        # Act
        results = await activity.get_by_url(async_session, test_url)

        # Assert
        assert len(results) == 1
        assert results[0].id == act.id
        assert results[0].url == test_url

    async def test_get_by_url_multiple_results(self, async_session: AsyncSession):
        """Test getting multiple activities with same url but different temporal."""
        # Arrange
        test_url = "http://example.com/multi-listing"
        await ActivityFactory.create_async(
            async_session,
            url=test_url,
            temporal_start_date_time=datetime(2025, 6, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 6, 8, 12, 0, 0),
        )
        await ActivityFactory.create_async(
            async_session,
            url=test_url,
            temporal_start_date_time=datetime(2025, 7, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 7, 8, 12, 0, 0),
        )

        # Act
        results = await activity.get_by_url(async_session, test_url)

        # Assert
        assert len(results) == 2
        assert all(r.url == test_url for r in results)

    async def test_get_by_url_not_found(self, async_session: AsyncSession):
        """Test getting activities by non-existent url."""
        # Act
        results = await activity.get_by_url(
            async_session, "http://example.com/nonexistent"
        )

        # Assert
        assert len(results) == 0

    async def test_get_by_url_with_limit(self, async_session: AsyncSession):
        """Test getting activities by url with explicit limit."""
        test_url = "http://example.com/limited-url"
        await ActivityFactory.create_async(async_session, url=test_url)
        await ActivityFactory.create_async(async_session, url=test_url)

        results = await activity.get_by_url(async_session, test_url, limit=1)

        assert len(results) == 1

    async def test_get_by_registration_number(self, async_session: AsyncSession):
        """Test getting activities by registration number."""
        # Arrange
        test_reg_number = "REG555555"
        act = await ActivityFactory.create_async(
            async_session, registration_number=test_reg_number
        )

        # Act
        results = await activity.get_by_registration_number(
            async_session, test_reg_number
        )

        # Assert
        assert len(results) == 1
        assert results[0].id == act.id
        assert results[0].registration_number == test_reg_number

    async def test_get_by_registration_number_not_found(
        self, async_session: AsyncSession
    ):
        """Test getting activities by non-existent registration number."""
        # Act
        results = await activity.get_by_registration_number(
            async_session, "NONEXISTENT"
        )

        # Assert
        assert len(results) == 0

    async def test_get_by_platform_id(self, async_session: AsyncSession):
        """Test getting activities by platform_id (foreign key)."""
        # Arrange
        platform = await PlatformFactory.create_async(async_session)
        _act1 = await ActivityFactory.create_async(
            async_session, platform_id=platform.id
        )
        _act2 = await ActivityFactory.create_async(
            async_session, platform_id=platform.id
        )

        # Act
        results = await activity.get_by_platform_id(async_session, platform.id)

        # Assert
        assert len(results) == 2
        assert all(r.platform_id == platform.id for r in results)

    async def test_get_by_platform_id_not_found(self, async_session: AsyncSession):
        """Test getting activities by non-existent platform_id."""
        # Act
        results = await activity.get_by_platform_id(
            async_session, 99999
        )  # platform_id is still int

        # Assert
        assert len(results) == 0

    async def test_get_by_area_id(self, async_session: AsyncSession):
        """Test getting activities by area_id (foreign key)."""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        _act1 = await ActivityFactory.create_async(async_session, area_id=area.id)
        _act2 = await ActivityFactory.create_async(async_session, area_id=area.id)

        # Act
        results = await activity.get_by_area_id(async_session, area.id)

        # Assert
        assert len(results) == 2
        assert all(r.area_id == area.id for r in results)

    async def test_get_by_area_id_not_found(self, async_session: AsyncSession):
        """Test getting activities by non-existent area_id."""
        # Act
        results = await activity.get_by_area_id(async_session, 99999)

        # Assert
        assert len(results) == 0

    async def test_get_by_activity_id(self, async_session: AsyncSession):
        """Test getting activity by functional activity_id (UUID)."""
        # Arrange
        _activity_id = "550e8400-e29b-41d4-a716-446655440000"
        act = await ActivityFactory.create_async(async_session)
        # Store the auto-generated ID
        generated_id = act.activity_id

        # Act
        result = await activity.get_by_activity_id(async_session, generated_id)

        # Assert
        assert result is not None
        assert result.activity_id == generated_id
        assert result.id == act.id

    async def test_get_by_activity_id_not_found(self, async_session: AsyncSession):
        """Test getting activity by non-existent activity_id."""
        # Act
        result = await activity.get_by_activity_id(
            async_session, "00000000-0000-0000-0000-000000000000"
        )

        # Assert
        assert result is None

    async def test_exists_any_by_activity_id_true_for_ended(
        self, async_session: AsyncSession
    ):
        """Test exists_any_by_activity_id returns True for an activity with ended_at set."""
        # Arrange
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session,
            activity_id="ended-activity-id",
            platform_id=platform.id,
        )
        await activity.mark_as_ended(async_session, "ended-activity-id", platform.id)

        # Act
        result = await activity.exists_any_by_activity_id(
            async_session, "ended-activity-id"
        )

        # Assert
        assert result is True

    async def test_exists_any_by_activity_id_false_for_nonexistent(
        self, async_session: AsyncSession
    ):
        """Test exists_any_by_activity_id returns False for non-existent activity_id."""
        # Act
        result = await activity.exists_any_by_activity_id(
            async_session, "00000000-0000-0000-0000-000000000000"
        )

        # Assert
        assert result is False

    async def test_get_current_by_activity_ids_returns_current_only(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)
        current = await ActivityFactory.create_async(
            async_session,
            activity_id="current-activity-id",
            platform_id=platform.id,
            area_id=area.id,
        )
        ended = await ActivityFactory.create_async(
            async_session,
            activity_id="ended-activity-id",
            platform_id=platform.id,
            area_id=area.id,
        )
        await activity.mark_as_ended(async_session, ended.activity_id, platform.id)

        result = await activity.get_current_by_activity_ids(
            async_session,
            [current.activity_id, ended.activity_id, "missing-activity-id"],
            platform.id,
        )

        assert result == {current.activity_id: True}

    async def test_get_deactivated_activity_ids_returns_only_ended_entities(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session,
            activity_id="current-activity-id",
            platform_id=platform.id,
            area_id=area.id,
        )
        await ActivityFactory.create_async(
            async_session,
            activity_id="ended-activity-id",
            platform_id=platform.id,
            area_id=area.id,
        )
        await activity.mark_as_ended(async_session, "ended-activity-id", platform.id)

        result = await activity.get_deactivated_activity_ids(
            async_session,
            ["current-activity-id", "ended-activity-id", "missing-activity-id"],
        )

        assert result == {"ended-activity-id"}

    async def test_activity_query_helpers_with_limit_and_bulk_mutations(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)

        reg_one = await ActivityFactory.create_async(
            async_session,
            registration_number="LIMIT-REG",
            platform_id=platform.id,
            area_id=area.id,
        )
        reg_two = await ActivityFactory.create_async(
            async_session,
            registration_number="LIMIT-REG",
            platform_id=platform.id,
            area_id=area.id,
        )

        reg_results = await activity.get_by_registration_number(
            async_session, "LIMIT-REG", limit=1
        )
        platform_results = await activity.get_by_platform_id(
            async_session, platform.id, limit=1
        )
        area_results = await activity.get_by_area_id(async_session, area.id, limit=1)

        assert len(reg_results) == 1
        assert reg_results[0].id in {reg_one.id, reg_two.id}
        assert len(platform_results) == 1
        assert len(area_results) == 1

        await activity.bulk_mark_as_ended(
            async_session,
            [reg_one.activity_id, reg_two.activity_id],
            platform.id,
        )
        ended_ids = await activity.get_deactivated_activity_ids(
            async_session, [reg_one.activity_id, reg_two.activity_id]
        )
        assert reg_one.activity_id in ended_ids
        assert reg_two.activity_id in ended_ids

        area_two = await AreaFactory.create_async(async_session)
        created_objects = await activity.bulk_create(
            async_session,
            [
                ActivityBulkCreate.model_validate(
                    {
                        "activityId": "bulk-created-activity",
                        "activityName": None,
                        "status": ActivityStatus.finished,
                        "areaId": area_two.area_id,
                        "url": "http://example.com/bulk-created",
                        "address": {
                            "thoroughfare": "Bulk Street",
                            "locatorDesignatorNumber": 1,
                            "locatorDesignatorLetter": None,
                            "locatorDesignatorAddition": None,
                            "postCode": "1234AB",
                            "postName": "Amsterdam",
                            "fullAddress": "Bulk Street 1, 1234AB Amsterdam",
                        },
                        "registrationNumber": "BULK-REG",
                        "numberOfGuests": 1,
                        "countryOfGuests": ["NLD"],
                        "temporal": {
                            "startDatetime": "2025-08-01T12:00:00",
                            "endDatetime": "2025-08-02T12:00:00",
                        },
                        "platform_technical_id": platform.id,
                        "area_technical_id": area_two.id,
                        "created_at": datetime(2025, 8, 1, 11, 0, 0),
                    }
                )
            ],
            platform,
            {area_two.area_id: area_two},
        )

        created = await activity.get_by_activity_id(
            async_session, "bulk-created-activity"
        )
        assert created is not None
        assert len(created_objects) == 1
        assert created_objects[0].activity_id == "bulk-created-activity"
        assert created_objects[0].platform is platform
        assert created_objects[0].area is area_two

    async def test_unique_constraint_activity_id_platform_id_created_at(
        self, async_session: AsyncSession
    ):
        """Test unique constraint on (activity_id, platform_id, created_at)."""
        import asyncio
        import uuid
        from datetime import datetime

        # Arrange
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)
        activity_id = str(uuid.uuid4())

        # Act - Create first activity
        act1 = await activity.create(
            session=async_session,
            activity_id=activity_id,
            activity_name="Version 1",
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/versioned-listing",
            address_thoroughfare="Main Street",
            address_locator_designator_number=123,
            address_locator_designator_letter=None,
            address_locator_designator_addition=None,
            address_post_code="1234AB",
            address_post_name="Amsterdam",
            address_full_address="Main Street 123, 1234AB Amsterdam",
            registration_number="REG123",
            number_of_guests=4,
            country_of_guests=["NLD"],
            temporal_start_date_time=datetime(2025, 6, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 6, 8, 12, 0, 0),
        )
        await async_session.commit()

        # Wait to ensure different timestamp (1 second to guarantee SQLite timestamp difference)
        await asyncio.sleep(1.0)

        # Act - Create second activity with same activity_id (should work due to different created_at)
        act2 = await activity.create(
            session=async_session,
            activity_id=activity_id,
            activity_name="Version 2",
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/versioned-listing-v2",
            address_thoroughfare="Main Street",
            address_locator_designator_number=123,
            address_locator_designator_letter=None,
            address_locator_designator_addition=None,
            address_post_code="1234AB",
            address_post_name="Amsterdam",
            address_full_address="Main Street 123, 1234AB Amsterdam",
            registration_number="REG124",
            number_of_guests=5,
            country_of_guests=["NLD", "DEU"],
            temporal_start_date_time=datetime(2025, 7, 1, 12, 0, 0),
            temporal_end_date_time=datetime(2025, 7, 8, 12, 0, 0),
        )

        # Assert
        assert act1.activity_id == act2.activity_id
        assert act1.id != act2.id  # Different technical IDs
        assert act1.created_at != act2.created_at  # Different timestamps
