"""Tests for CA Activities API endpoint (GET)."""

from typing import Any

import pytest
import pytest_asyncio
from app.api.v0.main import app_v0
from app.db.config import get_async_db_read_only
from app.security import verify_bearer_token
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
    """Mock token verification for testing with ca role and competent authority ID."""
    return {
        "sub": "test_user",
        "client_id": "0363",  # Competent authority ID for Gemeente Amsterdam
        "client_name": "Gemeente Amsterdam",
        "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
    }


@pytest.mark.database
class TestCAActivitiesAPI:
    """Test suite for GET /ca/activities API endpoint."""

    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        """Setup dependency overrides for authenticated tests."""
        # Override token verification
        app_v0.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

        # Override database session with read-only session
        async def override_get_db_read_only():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db_read_only

        yield

        # Clean up overrides after test
        app_v0.dependency_overrides.clear()

    @pytest.fixture
    def setup_db_only(self, async_session: AsyncSession):
        """Setup database override only (no auth override)."""

        # Override database session with read-only session
        async def override_get_db_read_only():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db_read_only

        yield

        # Clean up overrides after test
        app_v0.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def test_data(self, async_session: AsyncSession):
        """Create test data for CA activities tests."""
        # Create competent authorities
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

        # Create areas
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

        # Create platforms
        platform_str01 = await PlatformFactory.create_async(
            async_session, platform_id="str01", platform_name="Platform 01"
        )
        platform_str02 = await PlatformFactory.create_async(
            async_session, platform_id="str02", platform_name="Platform 02"
        )

        # Create activities for Amsterdam
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

        # Create activities for Den Haag
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
            "activities_amsterdam": activities_amsterdam,
            "activities_denhaag": activities_denhaag,
        }

    async def test_get_activities_success(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities returns activities (scoped to current logged-in competent authority) 0363."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activities" in data
        # Should return only Amsterdam data (competent authority 0363)
        assert len(data["activities"]) == 5

        # Verify response structure
        activity = data["activities"][0]
        assert "url" in activity
        assert "address" in activity
        assert "registrationNumber" in activity
        assert "areaId" in activity
        assert "numberOfGuests" in activity
        assert "countryOfGuests" in activity
        assert "temporal" in activity
        assert "platformId" in activity
        assert "platformName" in activity
        assert "createdAt" in activity

    async def test_get_activities_with_pagination(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities with pagination parameters."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act - get first page
            response1 = await client.get(
                "/ca/activities?offset=0&limit=2",
                headers={"Authorization": "Bearer test_token"},
            )
            # Act - get second page
            response2 = await client.get(
                "/ca/activities?offset=2&limit=2",
                headers={"Authorization": "Bearer test_token"},
            )
            # Act - get third page
            response3 = await client.get(
                "/ca/activities?offset=4&limit=2",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response3.status_code == status.HTTP_200_OK

        data1 = response1.json()
        data2 = response2.json()
        data3 = response3.json()

        assert len(data1["activities"]) == 2
        assert len(data2["activities"]) == 2
        assert len(data3["activities"]) == 1

        # Verify different activities in each page
        urls1 = {activity["url"] for activity in data1["activities"]}
        urls2 = {activity["url"] for activity in data2["activities"]}
        urls3 = {activity["url"] for activity in data3["activities"]}

        assert len(urls1 & urls2) == 0  # No overlap between page 1 and 2
        assert len(urls2 & urls3) == 0  # No overlap between page 2 and 3

    async def test_get_activities_empty_result(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/activities returns empty list when no data exists (scoped to current logged-in competent authority)."""
        # No test data created, so should return empty
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activities" in data
        assert len(data["activities"]) == 0

    async def test_get_activities_without_authentication(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /ca/activities without authentication token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get("/ca/activities")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_activities_with_invalid_offset(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities with negative offset."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities?offset=-1",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == 400

    async def test_get_activities_with_invalid_limit(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities with limit exceeding maximum."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities?limit=1001",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == 400

    async def test_get_activities_with_zero_limit(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities with limit=0."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities?limit=0",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == 400

    async def test_get_activities_default_unlimited(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities without limit parameter returns all data."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return all 5 Amsterdam activities (default is unlimited)
        assert len(data["activities"]) == 5

    async def test_get_activities_response_format(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities response has correct format with all required fields."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities?limit=1",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["activities"]) == 1

        activity = data["activities"][0]

        # Verify top-level fields
        assert isinstance(activity["url"], str)
        assert isinstance(activity["registrationNumber"], str)
        assert isinstance(
            activity["areaId"], str
        )  # areaId is technical ID (20-char UUID)
        assert isinstance(activity["numberOfGuests"], int)
        assert isinstance(activity["countryOfGuests"], list)
        assert isinstance(activity["platformId"], str)
        assert isinstance(activity["platformName"], str)
        assert isinstance(activity["createdAt"], str)

        # Verify address composite
        assert "address" in activity
        address = activity["address"]
        assert isinstance(address["street"], str)
        assert isinstance(address["number"], int)
        assert isinstance(address["postalCode"], str)
        assert isinstance(address["city"], str)
        # letter and addition are optional

        # Verify temporal composite
        assert "temporal" in activity
        temporal = activity["temporal"]
        assert isinstance(temporal["startDatetime"], str)
        assert isinstance(temporal["endDatetime"], str)

    async def test_count_activities_empty_database(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/activities/count when database is empty."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    async def test_count_activities_single(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/activities/count with single activity"""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        area = await AreaFactory.create_async(
            async_session,
            area_id="550e8400-e29b-41d4-a716-446655440003",
            area_name="Amsterdam Area",
            competent_authority_id=ca.id,
            filename="amsterdam.zip",
            filedata=b"amsterdam_data",
        )
        platform = await PlatformFactory.create_async(
            async_session, platform_id="str01", platform_name="Platform 01"
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/listing-1",
            area_id=area.id,
            registration_number="REG-001",
            platform_id=platform.id,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1

    async def test_count_activities_multiple(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test GET /ca/activities/count with multiple activities."""
        # test_data fixture creates 5 Amsterdam activities + 3 Den Haag activities
        # but token has client_id="0363" (Amsterdam) so should only return 5
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 5

    async def test_count_activities_response_structure(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test that count response structure matches OpenAPI specification."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify structure
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

        # Verify no extra keys
        assert set(data.keys()) == {"count"}

    async def test_count_activities_without_authentication(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /ca/activities/count without authentication token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get("/ca/activities/count")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_count_activities_with_invalid_token(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /ca/activities/count with invalid authentication token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/ca/activities/count",
                headers={"Authorization": "Bearer invalid_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_activities_without_ca_role(
        self, async_session: AsyncSession, test_data
    ):
        """Test GET /ca/activities without 'sdep_ca' role returns 403 Forbidden."""

        # Override token verification with mock that doesn't have 'sdep_ca' role
        def mock_token_without_ca_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "0363",
                "client_name": "Gemeente Amsterdam",
                "realm_access": {
                    "roles": ["sdep_read"]  # Missing 'sdep_ca' role
                },
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_ca_role

        # Override database session
        async def override_get_db_read_only():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db_read_only

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_v0), base_url="http://test"
            ) as client:
                # Act
                response = await client.get(
                    "/ca/activities",
                    headers={"Authorization": "Bearer test_token"},
                )

            # Assert
            assert response.status_code == status.HTTP_403_FORBIDDEN
            detail_msg = response.json()["detail"][0]["msg"].lower()
            assert "sdep_ca" in detail_msg
        finally:
            # Clean up overrides
            app_v0.dependency_overrides.clear()

    async def test_get_activities_without_client_id_claim(
        self, async_session: AsyncSession, test_data
    ):
        """Test GET /ca/activities without 'client_id' claim returns 401 Unauthorized."""

        # Override token verification with mock that doesn't have 'client_id' claim
        def mock_token_without_client_id() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
                # Missing 'client_id' claim
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_client_id

        # Override database session
        async def override_get_db_read_only():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db_read_only

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_v0), base_url="http://test"
            ) as client:
                # Act
                response = await client.get(
                    "/ca/activities",
                    headers={"Authorization": "Bearer test_token"},
                )

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            detail_msg = response.json()["detail"][0]["msg"].lower()
            assert "client_id" in detail_msg
        finally:
            # Clean up overrides
            app_v0.dependency_overrides.clear()

    async def test_count_activities_without_ca_role(
        self, async_session: AsyncSession, test_data
    ):
        """Test GET /ca/activities/count without 'sdep_ca' role returns 403 Forbidden."""

        # Override token verification with mock that doesn't have 'sdep_ca' role
        def mock_token_without_ca_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "0363",
                "client_name": "Gemeente Amsterdam",
                "realm_access": {
                    "roles": ["sdep_read"]  # Missing 'sdep_ca' role
                },
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_ca_role

        # Override database session
        async def override_get_db_read_only():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db_read_only

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_v0), base_url="http://test"
            ) as client:
                # Act
                response = await client.get(
                    "/ca/activities/count",
                    headers={"Authorization": "Bearer test_token"},
                )

            # Assert
            assert response.status_code == status.HTTP_403_FORBIDDEN
            detail_msg = response.json()["detail"][0]["msg"].lower()
            assert "sdep_ca" in detail_msg
        finally:
            # Clean up overrides
            app_v0.dependency_overrides.clear()

    async def test_count_activities_without_client_id_claim(
        self, async_session: AsyncSession, test_data
    ):
        """Test GET /ca/activities/count without 'client_id' claim returns 401 Unauthorized."""

        # Override token verification with mock that doesn't have 'client_id' claim
        def mock_token_without_client_id() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
                # Missing 'client_id' claim
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_client_id

        # Override database session
        async def override_get_db_read_only():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db_read_only

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_v0), base_url="http://test"
            ) as client:
                # Act
                response = await client.get(
                    "/ca/activities/count",
                    headers={"Authorization": "Bearer test_token"},
                )

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            detail_msg = response.json()["detail"][0]["msg"].lower()
            assert "client_id" in detail_msg
        finally:
            # Clean up overrides
            app_v0.dependency_overrides.clear()

    async def test_get_activities_response_does_not_contain_ended_at(
        self, async_session: AsyncSession, setup_overrides, test_data
    ):
        """Test that GET /ca/activities response does NOT contain endedAt (internal only)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/activities?limit=1",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["activities"]) == 1
        activity = data["activities"][0]
        assert "endedAt" not in activity
        assert "ended_at" not in activity
