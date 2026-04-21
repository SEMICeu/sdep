"""Tests for Activity business service"""

import pytest
from app.enums import ActivityStatus
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
        assert result[0]["status"] == "finished"
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
            "status",
            "platform_id",
            "platform_name",
            "url",
            "address_thoroughfare",
            "address_locator_designator_number",
            "address_locator_designator_letter",
            "address_locator_designator_addition",
            "address_post_code",
            "address_post_name",
            "address_full_address",
            "registration_number",
            "area_id",
            "competent_authority_id",
            "competent_authority_name",
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

    async def test_get_activity_list_includes_cancelled_status(
        self, async_session: AsyncSession
    ):
        """Test that cancelled current activities are returned with their lifecycle status."""
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session,
            area_id=area.id,
            platform_id=platform.id,
            status=ActivityStatus.cancelled,
        )

        result = await activity_service.get_activity_list(async_session, "0363")

        assert len(result) == 1
        assert result[0]["status"] == "cancelled"
