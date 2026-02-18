"""Tests for STR Activities API endpoint."""

from typing import Any

import pytest
import pytest_asyncio
from app.api.v0.main import app_v0
from app.crud import activity as activity_crud
from app.db.config import get_async_db, get_async_db_read_only
from app.security import verify_bearer_token
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory, CompetentAuthorityFactory


def mock_verify_bearer_token() -> dict[str, Any]:
    """Mock token verification for testing with str role."""
    return {
        "sub": "test_user",
        "client_id": "str01",
        "client_name": "STR Platform 01",
        "realm_access": {"roles": ["sdep_str", "sdep_read", "sdep_write"]},
    }


@pytest.mark.database
class TestSTRActivitiesAPI:
    """Test suite for POST /str/activities API endpoint."""

    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        """Setup dependency overrides for authenticated tests."""
        app_v0.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db
        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

        app_v0.dependency_overrides.clear()

    @pytest.fixture
    def setup_db_only(self, async_session: AsyncSession):
        """Setup database override only (no auth override)."""

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db
        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

        app_v0.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def test_areas(self, async_session: AsyncSession):
        """Create test areas for activities tests."""
        from app.crud import area as area_crud
        from app.crud import competent_authority as ca_crud

        ca = await ca_crud.get_by_competent_authority_id(async_session, "test")
        if ca is None:
            ca = await CompetentAuthorityFactory.create_async(
                async_session,
                competent_authority_id="test",
                competent_authority_name="Test Authority",
            )

        area_configs = [
            ("0363", "550e8400-e29b-41d4-a716-446655440001"),
            ("0344", "550e8400-e29b-41d4-a716-446655440002"),
            ("ceaba747-15ca-4d8a-81f7", "550e8400-e29b-41d4-a716-446655440003"),
            ("ceaba747-15ca", "550e8400-e29b-41d4-a716-446655440004"),
        ]

        areas = {}
        for key, area_uuid in area_configs:
            existing_area = await area_crud.get_by_area_id(async_session, area_uuid)
            if existing_area:
                areas[key] = existing_area
            else:
                area = await AreaFactory.create_async(
                    async_session,
                    area_id=area_uuid,
                    area_name=f"Test Area {key}",
                    competent_authority_id=ca.id,
                    filename=f"{key}.zip",
                    filedata=b"test_data",
                )
                areas[key] = area

        return areas

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup_activities(self, async_session: AsyncSession):
        """Setup fixture for test isolation."""
        yield

    async def test_post_activity_success(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test POST /str/activities with a single activity."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/listing-001",
                    "registrationNumber": "REG123456",
                    "address": {
                        "street": "Turfmarkt",
                        "number": 147,
                        "postalCode": "2500EA",
                        "city": "Den Haag",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NLD", "DEU", "BEL"],
                    "numberOfGuests": 4,
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "activityId" in data
        assert "createdAt" in data
        assert data["platformId"] == "str01"
        assert data["platformName"] == "STR Platform 01"
        assert data["areaId"] == test_areas["0363"].area_id
        assert data["url"] == "http://example.com/listing-001"
        assert data["registrationNumber"] == "REG123456"
        assert data["address"]["street"] == "Turfmarkt"
        assert data["address"]["number"] == 147
        assert data["address"]["postalCode"] == "2500EA"
        assert data["address"]["city"] == "Den Haag"
        assert data["temporal"]["startDatetime"] is not None
        assert data["temporal"]["endDatetime"] is not None
        assert data["countryOfGuests"] == ["NLD", "DEU", "BEL"]
        assert data["numberOfGuests"] == 4

        # Verify data was saved
        saved = await activity_crud.get_by_url(
            async_session, "http://example.com/listing-001"
        )
        assert len(saved) == 1
        assert saved[0].registration_number == "REG123456"

    async def test_post_activity_with_activity_id(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test POST /str/activities with optional activityId and activityName."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "activityId": "550e8400-e29b-41d4-a716-446655440999",
                    "activityName": "Custom Activity Name",
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/listing-with-id",
                    "registrationNumber": "REG123456",
                    "address": {
                        "street": "Turfmarkt",
                        "number": 147,
                        "postalCode": "2500EA",
                        "city": "Den Haag",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NLD", "DEU", "BEL"],
                    "numberOfGuests": 4,
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["activityId"] == "550e8400-e29b-41d4-a716-446655440999"
        assert data["activityName"] == "Custom Activity Name"

        # Verify data was saved
        saved = await activity_crud.get_by_url(
            async_session, "http://example.com/listing-with-id"
        )
        assert len(saved) == 1
        assert saved[0].activity_id == "550e8400-e29b-41d4-a716-446655440999"
        assert saved[0].activity_name == "Custom Activity Name"

    async def test_post_activity_with_optional_fields(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test POST /str/activities with all optional fields populated."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["0344"].area_id,
                    "url": "http://example.com/listing-full",
                    "registrationNumber": "REGFULL",
                    "address": {
                        "street": "Main Street",
                        "number": 999,
                        "postalCode": "5000CC",
                        "city": "Utrecht",
                        "letter": "B",
                        "addition": "3rd floor",
                    },
                    "temporal": {
                        "startDatetime": "2025-07-01T14:00:00Z",
                        "endDatetime": "2025-07-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NLD", "DEU", "BEL", "FRA"],
                    "numberOfGuests": 8,
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["address"]["letter"] == "B"
        assert data["address"]["addition"] == "3rd floor"

    async def test_post_activity_without_authentication(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test POST /str/activities without authentication token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_post_activity_without_str_role(
        self, async_session: AsyncSession, test_areas
    ):
        """Test POST /str/activities without 'sdep_str' role returns 403."""

        def mock_verify_bearer_token_without_str_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "ca01",
                "client_name": "CA 01",
                "realm_access": {"roles": ["ca", "sdep_read"]},
            }

        app_v0.dependency_overrides[verify_bearer_token] = (
            mock_verify_bearer_token_without_str_role
        )

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/test-no-role",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data
        detail_str = str(data["detail"]).lower()
        assert "sdep_str" in detail_str
        assert "role" in detail_str

        app_v0.dependency_overrides.clear()

    async def test_post_activity_without_client_id_claim(
        self, async_session: AsyncSession, test_areas
    ):
        """Test POST /str/activities without 'client_id' claim returns 401."""

        def mock_verify_bearer_token_without_client_id() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_name": "STR Platform 01",
                "realm_access": {"roles": ["sdep_str", "sdep_read", "sdep_write"]},
            }

        app_v0.dependency_overrides[verify_bearer_token] = (
            mock_verify_bearer_token_without_client_id
        )

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/test-no-client-id",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        detail_str = str(data["detail"]).lower()
        assert "client_id" in detail_str

        app_v0.dependency_overrides.clear()

    async def test_post_activity_validation_error_postal_code_with_space(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with invalid postal code (contains space)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "2500 EA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_end_before_start(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with end datetime before start datetime."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-07T14:00:00Z",
                        "endDatetime": "2025-06-01T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_letter_instead_of_number(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with letter instead of number for address.number field."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": "ABC",
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_letter_numeric_string(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with numeric string for address.letter field."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "letter": "6",
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_letter_special_char(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with special character for address.letter field."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "letter": "-",
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_postal_code_special_char(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with special character in postal code."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000-AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_country_code_lowercase(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with lowercase country code."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["nld"],
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_country_code_too_short(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with country code too short."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NL"],
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_country_code_too_long(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with country code too long."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["ABCD"],
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_country_code_with_numbers(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with country code containing numbers."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["N1D"],
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_validation_error_start_year_before_2025(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with start year before 2025."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area-id",
                    "url": "http://example.com/test",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2024-12-31T23:59:59Z",
                        "endDatetime": "2025-01-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422

    async def test_post_activity_platform_from_token(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test that platform is extracted from JWT token (client_id and client_name claims)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/test-platform-from-token",
                    "registrationNumber": "REGTOKEN",
                    "address": {
                        "street": "Test Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Test City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NLD"],
                    "numberOfGuests": 2,
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["platformId"] == "str01"
        assert data["platformName"] == "STR Platform 01"

    async def test_post_activity_nonexistent_area(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /str/activities with non-existent areaId returns 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "99999999-9999-9999-9999-999999999999",
                    "url": "http://example.com/test-nonexistent-area",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Check error message mentions area not found
        detail_str = str(data["detail"]).lower()
        assert "area" in detail_str
        assert "not found" in detail_str

    async def test_post_activity_area_id_with_hyphens(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test POST /str/activities accepts valid alphanumeric areaId with hyphens."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["ceaba747-15ca-4d8a-81f7"].area_id,
                    "url": "http://example.com/test-hex-hyphens",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NLD"],
                    "numberOfGuests": 2,
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["areaId"] == test_areas["ceaba747-15ca-4d8a-81f7"].area_id

    async def test_post_activity_validation_success_country_codes_alpha3(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test POST /str/activities accepts valid ISO 3166-1 alpha-3 country codes."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["ceaba747-15ca"].area_id,
                    "url": "http://example.com/test-alpha3-countries",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Main Street",
                        "number": 123,
                        "postalCode": "1000AA",
                        "city": "Amsterdam",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                    "countryOfGuests": ["NLD", "USA", "DEU", "GBR"],
                    "numberOfGuests": 4,
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["countryOfGuests"] == ["NLD", "USA", "DEU", "GBR"]

    async def test_post_activity_response_does_not_contain_ended_at(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test that POST /str/activities response does NOT contain endedAt (internal only)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/test-no-ended-at",
                    "registrationNumber": "REG123",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "endedAt" not in data
        assert "ended_at" not in data

    async def test_post_activity_versioning_returns_latest(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test that submitting same activityId twice returns latest version on POST."""
        import asyncio

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Submit v1
            response1 = await client.post(
                "/str/activities",
                json={
                    "activityId": "versioned-activity",
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/versioned-v1",
                    "registrationNumber": "REG-V1",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response1.status_code == status.HTTP_201_CREATED

            # Wait to ensure different timestamp (SQLite second precision)
            await asyncio.sleep(1.0)

            # Submit v2 with same activityId
            response2 = await client.post(
                "/str/activities",
                json={
                    "activityId": "versioned-activity",
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/versioned-v2",
                    "registrationNumber": "REG-V2",
                    "address": {
                        "street": "Street",
                        "number": 2,
                        "postalCode": "2000BB",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-07-01T14:00:00Z",
                        "endDatetime": "2025-07-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response2.status_code == status.HTTP_201_CREATED
            data = response2.json()
            assert data["activityId"] == "versioned-activity"
            assert data["url"] == "http://example.com/versioned-v2"

    # Tests for GET /str/activities

    async def test_get_own_activities_empty(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/activities returns empty list when no activities exist."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/str/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activities" in data
        assert data["activities"] == []

    async def test_get_own_activities_returns_own_activities(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test GET /str/activities returns activities only for the authenticated STR."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Create an activity for this STR
            await client.post(
                "/str/activities",
                json={
                    "activityId": "my-activity",
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/my-listing",
                    "registrationNumber": "REG-OWN",
                    "address": {
                        "street": "My Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "My City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

            # Get own activities
            response = await client.get(
                "/str/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["activities"]) == 1
        assert data["activities"][0]["activityId"] == "my-activity"
        # Should NOT contain platformId/Name (STR knows who it is)
        assert "platformId" not in data["activities"][0]
        assert "platformName" not in data["activities"][0]
        # Should NOT contain endedAt
        assert "endedAt" not in data["activities"][0]

    async def test_get_own_activities_does_not_return_other_str_activities(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test that GET /str/activities does NOT return activities from other STRs."""
        from tests.fixtures.factories import (
            ActivityFactory,
            AreaFactory,
            CompetentAuthorityFactory,
            PlatformFactory,
        )

        # Create activity for another STR directly
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="other-ca",
            competent_authority_name="Other CA",
        )
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="other.zip",
            filedata=b"data",
        )
        other_platform = await PlatformFactory.create_async(
            async_session,
            platform_id="other-str",
            platform_name="Other STR Platform",
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/other-str-listing",
            area_id=area.id,
            registration_number="REG-OTHER",
            platform_id=other_platform.id,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/str/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["activities"] == []  # STR "str01" has no activities

    async def test_get_own_activities_forbidden_missing_read_role(
        self, async_session: AsyncSession
    ):
        """Test GET /str/activities with missing sdep_read role."""

        def mock_token_without_read_role():
            return {
                "sub": "test_user",
                "client_id": "str01",
                "client_name": "STR Platform 01",
                "realm_access": {
                    "roles": ["sdep_str", "sdep_write"]
                },  # Missing sdep_read
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_read_role

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/str/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN

        app_v0.dependency_overrides.clear()

    # Tests for GET /str/activities/count

    async def test_count_own_activities_empty(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/activities/count returns 0 when no activities exist."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/str/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0

    async def test_count_own_activities_returns_correct_count(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test GET /str/activities/count returns correct count after creating activities."""
        import asyncio

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Create two activities for this STR
            await client.post(
                "/str/activities",
                json={
                    "activityId": "count-activity-1",
                    "areaId": test_areas["0363"].area_id,
                    "url": "http://example.com/count-1",
                    "registrationNumber": "REGCNT1",
                    "address": {
                        "street": "Street",
                        "number": 1,
                        "postalCode": "1000AA",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

            # Wait to ensure different timestamp (SQLite second precision)
            await asyncio.sleep(1.0)

            await client.post(
                "/str/activities",
                json={
                    "activityId": "count-activity-2",
                    "areaId": test_areas["0344"].area_id,
                    "url": "http://example.com/count-2",
                    "registrationNumber": "REGCNT2",
                    "address": {
                        "street": "Street",
                        "number": 2,
                        "postalCode": "2000BB",
                        "city": "City",
                    },
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

            # Count own activities
            response = await client.get(
                "/str/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2

    async def test_count_own_activities_does_not_count_other_str_activities(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Test that GET /str/activities/count does NOT count activities from other STRs."""
        from tests.fixtures.factories import (
            ActivityFactory,
            AreaFactory,
            CompetentAuthorityFactory,
            PlatformFactory,
        )

        # Create activity for another STR directly
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="other-ca-count",
            competent_authority_name="Other CA",
        )
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca.id,
            filename="other.zip",
            filedata=b"data",
        )
        other_platform = await PlatformFactory.create_async(
            async_session,
            platform_id="other-str-count",
            platform_name="Other STR Platform",
        )
        await ActivityFactory.create_async(
            async_session,
            url="http://example.com/other-str-count",
            area_id=area.id,
            registration_number="REG-OTHER-CNT",
            platform_id=other_platform.id,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/str/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0  # STR "str01" has no activities
