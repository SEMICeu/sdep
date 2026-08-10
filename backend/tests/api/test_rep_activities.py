"""Tests for REP Activities API endpoint (GET)."""

from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.rep.v1 import app_rep_v1
from app.db.config import get_async_db_read_only
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import (
    ActivityFactory,
    AreaFactory,
    CompetentAuthorityFactory,
    PlatformFactory,
)


def mock_verify_bearer_token() -> dict[str, Any]:
    """Mock token verification for testing with rep role."""
    return {
        "sub": "test_user",
        "client_id": "cbs01",
        "client_name": "Statistics Office",
        "realm_access": {"roles": ["sdep_rep", "sdep_read"]},
    }


@pytest.mark.database
class TestREPActivitiesAPI:
    """Test suite for GET /rep/activities API endpoint."""

    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        """Setup dependency overrides for authenticated tests."""
        app_rep_v1.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

        async def override_get_db_read_only():
            yield async_session

        app_rep_v1.dependency_overrides[get_async_db_read_only] = (
            override_get_db_read_only
        )

        yield

        app_rep_v1.dependency_overrides.clear()

    @pytest.fixture
    def setup_db_only(self, async_session: AsyncSession):
        """Setup database override only (no auth override)."""

        async def override_get_db_read_only():
            yield async_session

        app_rep_v1.dependency_overrides[get_async_db_read_only] = (
            override_get_db_read_only
        )

        yield

        app_rep_v1.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def test_data(self, async_session: AsyncSession):
        """Create cross-CA test data for REP activities tests."""
        ca_amsterdam = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        ca_denhaag = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0518",
            competent_authority_name="Gemeente Den Haag",
        )

        area_amsterdam = await AreaFactory.create_async(
            async_session,
            area_id="550e8400-e29b-41d4-a716-446655440001",
            area_name="Amsterdam Area",
            competent_authority_id=ca_amsterdam.id,
            filename="amsterdam.zip",
            filedata=b"amsterdam_data",
        )
        area_denhaag = await AreaFactory.create_async(
            async_session,
            area_id="550e8400-e29b-41d4-a716-446655440002",
            area_name="Den Haag Area",
            competent_authority_id=ca_denhaag.id,
            filename="denhaag.zip",
            filedata=b"denhaag_data",
        )

        platform_str01 = await PlatformFactory.create_async(
            async_session, platform_id="str01", platform_name="Platform 01"
        )
        platform_str02 = await PlatformFactory.create_async(
            async_session, platform_id="str02", platform_name="Platform 02"
        )

        activities_amsterdam = []
        for i in range(5):
            activity = await ActivityFactory.create_async(
                async_session,
                url=f"http://example.com/amsterdam-{i}",
                area_id=area_amsterdam.id,
                registration_number=f"REG-AMS-{i:03d}",
                platform_id=platform_str01.id,
            )
            activities_amsterdam.append(activity)

        activities_denhaag = []
        for i in range(3):
            activity = await ActivityFactory.create_async(
                async_session,
                url=f"http://example.com/denhaag-{i}",
                area_id=area_denhaag.id,
                registration_number=f"REG-DH-{i:03d}",
                platform_id=platform_str02.id,
            )
            activities_denhaag.append(activity)

        return {
            "ca_amsterdam": ca_amsterdam,
            "ca_denhaag": ca_denhaag,
            "area_amsterdam": area_amsterdam,
            "area_denhaag": area_denhaag,
            "platform_str01": platform_str01,
            "platform_str02": platform_str02,
            "activities_amsterdam": activities_amsterdam,
            "activities_denhaag": activities_denhaag,
        }

    async def test_get_activities_returns_all_competent_authorities(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities returns activities across all competent authorities."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activities" in data
        # Unlike the CA API, the REP API is not scoped: both CAs are visible
        assert len(data["activities"]) == 8
        competent_authority_ids = {
            activity["competentAuthorityId"] for activity in data["activities"]
        }
        assert competent_authority_ids == {"0363", "0518"}

        # Verify the required REP activity fields are present
        activity = data["activities"][0]
        assert "temporal" in activity
        assert "startDatetime" in activity["temporal"]
        assert "endDatetime" in activity["temporal"]
        assert "numberOfGuests" in activity
        assert "countryOfGuests" in activity
        assert "registrationNumber" in activity
        assert "competentAuthorityId" in activity
        assert "competentAuthorityName" in activity
        activities_by_url = {
            activity["url"]: activity for activity in data["activities"]
        }
        assert (
            activities_by_url["http://example.com/amsterdam-0"]["areaName"]
            == "Amsterdam Area"
        )
        assert (
            activities_by_url["http://example.com/denhaag-0"]["areaName"]
            == "Den Haag Area"
        )

    async def test_get_activities_excludes_ended_versions(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities excludes soft-deleted (ended) activity versions."""
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/ended",
            area_id=test_data["area_amsterdam"].id,
            platform_id=test_data["platform_str01"].id,
            ended_at=datetime(2026, 5, 21, 10, 0, 0),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["activities"]) == 8
        urls = {activity["url"] for activity in data["activities"]}
        assert "http://example.com/ended" not in urls

    async def test_get_activities_with_pagination(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities with pagination parameters."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response1 = await client.get(
                "/activities?offset=0&limit=5",
                headers={"Authorization": "Bearer test_token"},
            )
            response2 = await client.get(
                "/activities?offset=5&limit=5",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        page1 = response1.json()["activities"]
        page2 = response2.json()["activities"]
        assert len(page1) == 5
        assert len(page2) == 3
        # No overlap between pages
        urls1 = {activity["url"] for activity in page1}
        urls2 = {activity["url"] for activity in page2}
        assert urls1.isdisjoint(urls2)

    async def test_get_activities_rejects_limit_above_maximum(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities rejects limit above the maximum of 1000."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities?limit=1001",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 400

    async def test_get_activities_applies_default_limit(
        self, async_session: AsyncSession, setup_overrides, monkeypatch
    ):
        """Test GET /rep/activities applies the default limit of 1000."""
        captured: dict[str, Any] = {}

        async def fake_get_activity_list(session, *, client_id, offset, limit, filters):
            captured["offset"] = offset
            captured["limit"] = limit
            return []

        monkeypatch.setattr(
            "app.api.common.activity_handlers.activity.get_activity_list",
            fake_get_activity_list,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert captured == {"offset": 0, "limit": 1000}

    async def test_get_activities_with_filters(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities filters by createdAt range, platformId, and areaId."""
        expected = await ActivityFactory.create_async(
            async_session,
            url="http://example.com/expected",
            area_id=test_data["area_amsterdam"].id,
            platform_id=test_data["platform_str01"].id,
            created_at=datetime(2026, 5, 21, 10, 0, 0),
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/old",
            area_id=test_data["area_amsterdam"].id,
            platform_id=test_data["platform_str01"].id,
            created_at=datetime(2026, 5, 20, 10, 0, 0),
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/other-platform",
            area_id=test_data["area_amsterdam"].id,
            platform_id=test_data["platform_str02"].id,
            created_at=datetime(2026, 5, 21, 10, 0, 0),
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/other-area",
            area_id=test_data["area_denhaag"].id,
            platform_id=test_data["platform_str01"].id,
            created_at=datetime(2026, 5, 21, 10, 0, 0),
        )

        query = (
            "/activities"
            "?filterCreatedAtFrom=2026-05-21T00:00:00Z"
            "&filterCreatedAtTo=2026-05-22T00:00:00Z"
            "&filterPlatformId=str01"
            "&filterAreaId=550e8400-e29b-41d4-a716-446655440001"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                query,
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert [activity["url"] for activity in data["activities"]] == [expected.url]

    async def test_get_activities_filter_by_competent_authority(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities filters by competent authority functional ID."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities?filterCompetentAuthorityId=0518",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["activities"]) == 3
        assert all(
            activity["competentAuthorityId"] == "0518"
            for activity in data["activities"]
        )

    @pytest.mark.parametrize(
        ("query_param", "value"),
        [
            ("filterPlatformId", "invalid id"),
            ("filterAreaId", "invalid/id"),
            ("filterCompetentAuthorityId", "invalid id"),
        ],
    )
    async def test_get_activities_rejects_invalid_functional_id_filters(
        self,
        async_session: AsyncSession,
        setup_overrides,
        test_data,
        query_param: str,
        value: str,
    ):
        """Test GET /rep/activities validates functional ID query filters."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/activities?{query_param}={value}",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 400

    @pytest.mark.parametrize(
        ("query_param", "value"),
        [
            ("filterCreatedAtFrom", "2026-05-21T00:00:00"),
            ("filterCreatedAtFrom", "2026-05-21T00:00:00%2B02:00"),
            ("filterCreatedAtTo", "2026-05-21T00:00:00"),
            ("filterCreatedAtTo", "2026-05-21T00:00:00%2B02:00"),
        ],
    )
    async def test_get_activities_rejects_non_utc_created_at_filters(
        self,
        async_session: AsyncSession,
        setup_overrides,
        test_data,
        query_param: str,
        value: str,
    ):
        """Test GET /rep/activities only accepts UTC createdAt filters."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/activities?{query_param}={value}",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_get_activities_empty_result(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /rep/activities returns empty list when no data exists."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["activities"] == []

    async def test_count_activities(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities/count counts activities across all competent authorities."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 8

    async def test_count_activities_with_filters(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /rep/activities/count applies the same filters as the list endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response_match = await client.get(
                "/activities/count?filterCompetentAuthorityId=0363&filterPlatformId=str01",
                headers={"Authorization": "Bearer test_token"},
            )
            response_no_match = await client.get(
                "/activities/count?filterCompetentAuthorityId=0363&filterPlatformId=str02",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response_match.status_code == status.HTTP_200_OK
        assert response_match.json()["count"] == 5
        assert response_no_match.status_code == status.HTTP_200_OK
        assert response_no_match.json()["count"] == 0

    @pytest.mark.parametrize("path", ["/activities", "/activities/count"])
    async def test_get_activities_unauthorized(
        self, async_session: AsyncSession, setup_db_only, path: str
    ):
        """Test GET /rep endpoints without token returns 401 Unauthorized."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(path)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("path", ["/activities", "/activities/count"])
    async def test_get_activities_without_rep_role(
        self, async_session: AsyncSession, test_data, path: str
    ):
        """Test GET /rep endpoints without 'sdep_rep' role returns 403 Forbidden."""

        def mock_token_without_rep_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "0363",
                "client_name": "Gemeente Amsterdam",
                # A competent authority client cannot use the REP API
                "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
            }

        app_rep_v1.dependency_overrides[verify_bearer_token] = (
            mock_token_without_rep_role
        )

        async def override_get_db_read_only():
            yield async_session

        app_rep_v1.dependency_overrides[get_async_db_read_only] = (
            override_get_db_read_only
        )

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_rep_v1), base_url="http://test"
            ) as client:
                response = await client.get(
                    path,
                    headers={"Authorization": "Bearer test_token"},
                )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            detail_msg = response.json()["detail"][0]["msg"].lower()
            assert "sdep_rep" in detail_msg
        finally:
            app_rep_v1.dependency_overrides.clear()

    @pytest.mark.parametrize("path", ["/activities", "/activities/count"])
    async def test_get_activities_without_read_role(
        self, async_session: AsyncSession, test_data, path: str
    ):
        """Test GET /rep endpoints without 'sdep_read' role returns 403 Forbidden."""

        def mock_token_without_read_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "cbs01",
                "client_name": "Statistics Office",
                "realm_access": {"roles": ["sdep_rep"]},
            }

        app_rep_v1.dependency_overrides[verify_bearer_token] = (
            mock_token_without_read_role
        )

        async def override_get_db_read_only():
            yield async_session

        app_rep_v1.dependency_overrides[get_async_db_read_only] = (
            override_get_db_read_only
        )

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_rep_v1), base_url="http://test"
            ) as client:
                response = await client.get(
                    path,
                    headers={"Authorization": "Bearer test_token"},
                )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            detail_msg = response.json()["detail"][0]["msg"].lower()
            assert "sdep_read" in detail_msg
        finally:
            app_rep_v1.dependency_overrides.clear()

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/activities"),
            ("PUT", "/activities"),
            ("PATCH", "/activities"),
            ("DELETE", "/activities"),
            ("POST", "/activities/count"),
        ],
    )
    async def test_write_methods_not_allowed(
        self, async_session: AsyncSession, setup_overrides, method: str, path: str
    ):
        """Test that the REP API rejects all write methods with 405 Method Not Allowed."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.request(
                method,
                path,
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_get_activities_response_does_not_contain_ended_at(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test that the technical ended_at field is not exposed in the response."""
        async with AsyncClient(
            transport=ASGITransport(app=app_rep_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        activity = response.json()["activities"][0]
        assert "ended_at" not in activity
        assert "endedAt" not in activity
