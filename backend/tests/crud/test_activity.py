"""Tests for Activity CRUD operations."""

from datetime import datetime

import pytest
from app.crud import activity
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
        address_street = "Main Street"
        address_number = 123
        address_postal_code = "1234AB"
        address_city = "Amsterdam"
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
            address_street=address_street,
            address_number=address_number,
            address_letter=None,
            address_addition=None,
            address_postal_code=address_postal_code,
            address_city=address_city,
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
        assert result.url == url
        assert result.address_street == address_street
        assert result.address_number == address_number
        assert result.address_letter is None
        assert result.address_addition is None
        assert result.address_postal_code == address_postal_code
        assert result.address_city == address_city
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
            address_street="Auto Street",
            address_number=999,
            address_letter=None,
            address_addition=None,
            address_postal_code="9999ZZ",
            address_city="AutoCity",
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

    async def test_create_activity_with_optional_fields(
        self, async_session: AsyncSession
    ):
        """Test creating activity with optional address fields."""
        # Arrange
        area = await AreaFactory.create_async(async_session)
        platform = await PlatformFactory.create_async(async_session)
        address_letter = "A"
        address_addition = "1hoog"

        # Act
        result = await activity.create(
            session=async_session,
            activity_id="7c9e6679-7425-40de-944b-e07fc1f90ae7",
            activity_name="Rotterdam Rental",
            platform_id=platform.id,
            area_id=area.id,
            url="http://example.com/listing-2",
            address_street="Side Street",
            address_number=456,
            address_letter=address_letter,
            address_addition=address_addition,
            address_postal_code="5678CD",
            address_city="Rotterdam",
            registration_number="REG789012",
            number_of_guests=2,
            country_of_guests=["BEL"],
            temporal_start_date_time=datetime(2025, 7, 1, 14, 0, 0),
            temporal_end_date_time=datetime(2025, 7, 5, 14, 0, 0),
        )

        # Assert
        assert result.address_letter == address_letter
        assert result.address_addition == address_addition

    async def test_delete_activity(self, async_session: AsyncSession):
        """Test deleting an existing activity."""
        # Arrange
        act = await ActivityFactory.create_async(async_session)

        # Act
        result = await activity.delete(async_session, act.id)

        # Assert
        assert result is True
        retrieved = await activity.get_by_id(async_session, act.id)
        assert retrieved is None

    async def test_delete_activity_not_found(self, async_session: AsyncSession):
        """Test deleting a non-existent activity."""
        # Act
        result = await activity.delete(async_session, 99999)

        # Assert
        assert result is False

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

    async def test_get_by_competent_authority_id(self, async_session: AsyncSession):
        """Test getting activities by competent_authority_id."""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        act = await ActivityFactory.create_async(async_session, area_id=area.id)

        # Act
        results = await activity.get_by_competent_authority_id(async_session, "0363")

        # Assert
        assert len(results) == 1
        assert results[0].id == act.id

    async def test_get_by_competent_authority_id_not_found(
        self, async_session: AsyncSession
    ):
        """Test getting activities by non-existent competent_authority_id."""
        # Act
        results = await activity.get_by_competent_authority_id(async_session, "9999")

        # Assert
        assert len(results) == 0

    async def test_count_by_competent_authority_id(self, async_session: AsyncSession):
        """Test counting activities by competent_authority_id."""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0518",
            competent_authority_name="Gemeente Den Haag",
        )
        await ActivityFactory.create_async(async_session, area_id=area.id)
        await ActivityFactory.create_async(async_session, area_id=area.id)
        await ActivityFactory.create_async(async_session, area_id=area.id)

        # Act
        total = await activity.count_by_competent_authority_id(async_session, "0518")

        # Assert
        assert total == 3

    async def test_count_by_competent_authority_id_not_found(
        self, async_session: AsyncSession
    ):
        """Test counting activities by non-existent competent_authority_id."""
        # Act
        total = await activity.count_by_competent_authority_id(async_session, "9999")

        # Assert
        assert total == 0

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

    async def test_count_by_platform_id_str(self, async_session: AsyncSession):
        """Test counting activities by platform functional ID."""
        # Arrange
        platform = await PlatformFactory.create_async(
            async_session,
            platform_id="test-platform",
            platform_name="Test Platform",
        )
        for _ in range(3):
            await ActivityFactory.create_async(async_session, platform_id=platform.id)

        # Act
        total = await activity.count_by_platform_id_str(async_session, "test-platform")

        # Assert
        assert total == 3

    async def test_count_by_platform_id_str_not_found(
        self, async_session: AsyncSession
    ):
        """Test counting activities by non-existent platform functional ID."""
        # Act
        total = await activity.count_by_platform_id_str(
            async_session, "nonexistent-platform"
        )

        # Assert
        assert total == 0

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
            address_street="Main Street",
            address_number=123,
            address_letter=None,
            address_addition=None,
            address_postal_code="1234AB",
            address_city="Amsterdam",
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
            address_street="Main Street",
            address_number=123,
            address_letter=None,
            address_addition=None,
            address_postal_code="1234AB",
            address_city="Amsterdam",
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
