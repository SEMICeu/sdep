"""Tests for Areas API endpoint."""

from typing import Any

import pytest
import pytest_asyncio
from app.api.v0.main import app_v0
from app.db.config import get_async_db_read_only
from app.security import verify_bearer_token
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory, CompetentAuthorityFactory


def mock_verify_bearer_token() -> dict[str, Any]:
    """Mock token verification for testing."""
    return {"sub": "test_user", "realm_access": {"roles": ["sdep_str", "sdep_read"]}}


@pytest.mark.database
class TestStrAreaAPI:
    """Test suite for GET /str/areas API endpoint."""

    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        """Setup dependency overrides for authenticated tests."""
        # Override token verification
        app_v0.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

        # Override database session
        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

        # Clean up overrides after test
        app_v0.dependency_overrides.clear()

    @pytest.fixture
    def setup_db_only(self, async_session: AsyncSession):
        """Setup database override only (no auth override)."""

        # Override database session
        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

        # Clean up overrides after test
        app_v0.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def competent_authority(self, async_session: AsyncSession):
        """Create a test competent authority."""
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        return ca

    async def test_get_areas_empty_database(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas when database is empty."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "areas" in data
        assert data["areas"] == []

    async def test_get_areas_single_area(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas with single area."""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="Amsterdam.zip",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 1
        assert data["areas"][0]["competentAuthorityId"] == "0363"
        assert data["areas"][0]["competentAuthorityName"] == "Gemeente Amsterdam"
        assert data["areas"][0]["filename"] == "Amsterdam.zip"
        assert "areaId" in data["areas"][0]
        assert "createdAt" in data["areas"][0]

    async def test_get_areas_multiple_areas(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas with multiple areas."""
        # Arrange
        ca1 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0363",
            competent_authority_name="Gemeente Amsterdam",
        )
        ca2 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0599",
            competent_authority_name="Gemeente Rotterdam",
        )
        ca3 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0518",
            competent_authority_name="Gemeente Den Haag",
        )

        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca1.id,
            filename="Amsterdam.zip",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca2.id,
            filename="Rotterdam.zip",
        )
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=ca3.id,
            filename="Den_Haag.zip",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 3

        # Find each area
        authority_ids = [area["competentAuthorityId"] for area in data["areas"]]
        assert "0363" in authority_ids
        assert "0599" in authority_ids
        assert "0518" in authority_ids

    async def test_get_areas_response_structure(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test that response structure matches OpenAPI specification."""
        # Arrange
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="test.zip",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify top-level structure
        assert "areas" in data
        assert isinstance(data["areas"], list)

        # Verify area structure
        area = data["areas"][0]
        assert "areaId" in area
        assert "areaName" in area  # Optional functional name
        assert "competentAuthorityId" in area
        assert "competentAuthorityName" in area
        assert "filename" in area
        assert "createdAt" in area

        # Verify types
        assert isinstance(area["areaId"], str)
        assert len(area["areaId"]) == 36  # RFC 9562 UUID format
        assert isinstance(area["areaName"], (str, type(None)))  # Optional field
        assert isinstance(area["competentAuthorityId"], str)
        assert isinstance(area["competentAuthorityName"], str)
        assert isinstance(area["filename"], str)
        assert isinstance(area["createdAt"], str)

    async def test_get_areas_without_authentication(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /str/areas without authentication token."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get("/str/areas")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_areas_with_invalid_token(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /str/areas with invalid authentication token."""
        # Arrange - no auth override, so real auth will be used
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act - send invalid token
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer invalid_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_areas_content_type(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test that response has correct content type."""
        # Arrange
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"

    async def test_get_areas_with_pagination_offset(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas with offset pagination parameter."""
        # Arrange
        ca1 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0001",
            competent_authority_name="CA 1",
        )
        ca2 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0002",
            competent_authority_name="CA 2",
        )
        ca3 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0003",
            competent_authority_name="CA 3",
        )
        ca4 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0004",
            competent_authority_name="CA 4",
        )

        await AreaFactory.create_async(async_session, competent_authority_id=ca1.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca2.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca3.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca4.id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas?offset=2", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 2
        authority_ids = [area["competentAuthorityId"] for area in data["areas"]]
        assert "0003" in authority_ids
        assert "0004" in authority_ids

    async def test_get_areas_with_pagination_limit(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas with limit pagination parameter."""
        # Arrange
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas?limit=2", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 2

    async def test_get_areas_with_pagination_offset_and_limit(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas with both offset and limit pagination parameters."""
        # Arrange
        ca1 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0001",
            competent_authority_name="CA 1",
        )
        ca2 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0002",
            competent_authority_name="CA 2",
        )
        ca3 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0003",
            competent_authority_name="CA 3",
        )
        ca4 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0004",
            competent_authority_name="CA 4",
        )
        ca5 = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="0005",
            competent_authority_name="CA 5",
        )

        await AreaFactory.create_async(async_session, competent_authority_id=ca1.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca2.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca3.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca4.id)
        await AreaFactory.create_async(async_session, competent_authority_id=ca5.id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas?offset=1&limit=2",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 2
        authority_ids = [area["competentAuthorityId"] for area in data["areas"]]
        assert "0002" in authority_ids
        assert "0003" in authority_ids

    async def test_get_areas_pagination_offset_beyond_results(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas with offset beyond available results."""
        # Arrange
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas?offset=10", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 0

    async def test_get_areas_pagination_invalid_offset(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas with invalid offset parameter."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas?offset=-1", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_get_areas_pagination_invalid_limit(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas with invalid limit parameter."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act - limit must be between 1 and 1000
            response = await client.get(
                "/str/areas?limit=0", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_get_areas_pagination_limit_exceeds_max(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas with limit exceeding maximum."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act - max limit is 1000
            response = await client.get(
                "/str/areas?limit=2000", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_count_areas_empty_database(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas/count when database is empty."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas/count", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    async def test_count_areas_single(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas/count with single area."""
        # Arrange
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas/count", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1

    async def test_count_areas_multiple(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas/count with multiple areas."""
        # Arrange
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas/count", headers={"Authorization": "Bearer test_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 5

    async def test_count_areas_response_structure(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test that count response structure matches OpenAPI specification."""
        # Arrange
        await AreaFactory.create_async(
            async_session, competent_authority_id=competent_authority.id
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas/count", headers={"Authorization": "Bearer test_token"}
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

    async def test_count_areas_without_authentication(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /str/areas/count without authentication token."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get("/str/areas/count")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_count_areas_with_invalid_token(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test GET /str/areas/count with invalid authentication token."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas/count", headers={"Authorization": "Bearer invalid_token"}
            )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_area_not_found(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /str/areas/{areaId} when area does not exist."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                "/str/areas/99999999999999999999",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        # detail is a list of error objects
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        assert "99999999999999999999" in data["detail"][0]["msg"]

    async def test_get_area_with_data(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas/{areaId} with area containing data."""
        # Arrange
        test_data = b"test_binary_data"
        test_filename = "test_area.zip"
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename=test_filename,
            filedata=test_data,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                f"/str/areas/{area.area_id}",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.content == test_data
        assert response.headers["content-type"] == "application/zip"
        assert f'filename="{test_filename}"' in response.headers.get(
            "content-disposition", ""
        )

    async def test_get_area_without_authentication(
        self, async_session: AsyncSession, setup_db_only, competent_authority
    ):
        """Test GET /str/areas/{areaId} without authentication token."""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="test.zip",
            filedata=b"data",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(f"/str/areas/{area.area_id}")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_area_with_invalid_token(
        self, async_session: AsyncSession, setup_db_only, competent_authority
    ):
        """Test GET /str/areas/{areaId} with invalid authentication token."""
        # Arrange
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="test.zip",
            filedata=b"data",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                f"/str/areas/{area.area_id}",
                headers={"Authorization": "Bearer invalid_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_area_with_large_binary_data(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas/{areaId} with large binary content."""
        # Arrange
        large_data = b"x" * 10000  # 10KB of data
        area = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="large_area.zip",
            filedata=large_data,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act
            response = await client.get(
                f"/str/areas/{area.area_id}",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.content == large_data
        assert len(response.content) == 10000
        assert response.headers["content-type"] == "application/zip"

    async def test_get_area_multiple_areas_correct_isolation(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test GET /str/areas/{areaId} returns correct area when multiple exist."""
        # Arrange
        _area1 = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="area1.zip",
            filedata=b"data1",
        )
        area2 = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="area2.zip",
            filedata=b"data2",
        )
        _area3 = await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="area3.zip",
            filedata=b"data3",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Act - request middle area
            response = await client.get(
                f"/str/areas/{area2.area_id}",
                headers={"Authorization": "Bearer test_token"},
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"data2"
        assert response.headers["content-type"] == "application/zip"

    async def test_get_areas_response_does_not_contain_ended_at(
        self, async_session: AsyncSession, setup_overrides, competent_authority
    ):
        """Test that GET /str/areas response does NOT contain endedAt (internal only)."""
        await AreaFactory.create_async(
            async_session,
            competent_authority_id=competent_authority.id,
            filename="test.zip",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/str/areas", headers={"Authorization": "Bearer test_token"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 1
        area = data["areas"][0]
        assert "endedAt" not in area
        assert "ended_at" not in area
