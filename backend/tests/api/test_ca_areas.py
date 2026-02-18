"""Tests for CA Area API endpoints."""

from typing import Any

import pytest
from app.api.v0.main import app_v0
from app.db.config import get_async_db, get_async_db_read_only
from app.security import verify_bearer_token
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def mock_verify_bearer_token() -> dict[str, Any]:
    """Mock token verification for testing with ca role."""
    return {
        "sub": "test_user",
        "client_id": "0363",
        "client_name": "Gemeente Amsterdam",
        "realm_access": {"roles": ["sdep_ca", "sdep_read", "sdep_write"]},
    }


@pytest.mark.database
class TestCAAreaAPI:
    """Test suite for POST /ca/areas API endpoint."""

    @pytest.fixture(autouse=True)
    async def cleanup(self, async_session: AsyncSession):
        """Auto-cleanup fixture that runs before and after each test."""
        yield
        app_v0.dependency_overrides.clear()

    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        """Setup dependency overrides for authenticated tests."""
        app_v0.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db
        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

    @pytest.fixture
    def setup_db_only(self, async_session: AsyncSession):
        """Setup database override only (no auth override)."""

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db
        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

    # Tests for POST /ca/areas

    async def test_post_area_success(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /ca/areas with a single area file upload (201 Created)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "areaId" in data
        assert data["filename"] == "Area.zip"
        assert "createdAt" in data
        assert data["competentAuthorityId"] == "0363"
        assert data["competentAuthorityName"] == "Gemeente Amsterdam"

    async def test_post_area_with_area_id(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /ca/areas with custom areaId preserved."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                data={"areaId": "my-custom-id"},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["areaId"] == "my-custom-id"

    async def test_post_area_with_area_name(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /ca/areas with areaName."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                data={"areaName": "Amsterdam Central"},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["areaName"] == "Amsterdam Central"

    async def test_post_area_auto_generates_id(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /ca/areas without areaId generates a UUID."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "areaId" in data
        assert len(data["areaId"]) == 36  # UUID format

    async def test_post_area_creates_competent_authority(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test that POST /ca/areas auto-creates competent authority."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["competentAuthorityId"] == "0363"
        assert data["competentAuthorityName"] == "Gemeente Amsterdam"

    async def test_post_area_file_too_large(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /ca/areas with file exceeding 1 MiB returns 422."""
        large_data = b"x" * (1048576 + 1)  # 1 MiB + 1 byte

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Large.zip", large_data, "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_post_area_unauthorized_no_token(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test POST /ca/areas without authentication token."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_post_area_forbidden_missing_write_role(
        self, async_session: AsyncSession
    ):
        """Test POST /ca/areas with missing sdep_write role."""

        def mock_token_without_write_role():
            return {
                "sub": "test_user",
                "client_id": "0363",
                "client_name": "Gemeente Amsterdam",
                "realm_access": {
                    "roles": ["sdep_ca", "sdep_read"]
                },  # Missing sdep_write
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_write_role

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "sdep_write" in response.json()["detail"][0]["msg"]

    async def test_post_area_invalid_area_id_pattern(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test POST /ca/areas with invalid areaId pattern returns 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                data={"areaId": "INVALID_ID"},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_post_area_response_does_not_contain_ended_at(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test that POST /ca/areas response does NOT contain endedAt (internal only)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "endedAt" not in data
        assert "ended_at" not in data

    async def test_post_area_versioning_returns_latest(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test that submitting same areaId twice returns latest version on POST."""
        import asyncio

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Submit v1
            response1 = await client.post(
                "/ca/areas",
                files={"file": ("Area_v1.zip", b"zipdata_v1", "application/zip")},
                data={"areaId": "versioned-area"},
                headers={"Authorization": "Bearer test_token"},
            )
            assert response1.status_code == status.HTTP_201_CREATED

            # Wait to ensure different timestamp (SQLite second precision)
            await asyncio.sleep(1.0)

            # Submit v2 with same areaId
            response2 = await client.post(
                "/ca/areas",
                files={"file": ("Area_v2.zip", b"zipdata_v2", "application/zip")},
                data={"areaId": "versioned-area"},
                headers={"Authorization": "Bearer test_token"},
            )
            assert response2.status_code == status.HTTP_201_CREATED
            data = response2.json()
            assert data["areaId"] == "versioned-area"
            assert data["filename"] == "Area_v2.zip"

    # Tests for GET /ca/areas

    async def test_get_own_areas_empty(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/areas returns empty list when no areas exist."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "areas" in data
        assert data["areas"] == []

    async def test_get_own_areas_returns_own_areas(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/areas returns areas only for the authenticated CA."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Create an area for this CA
            await client.post(
                "/ca/areas",
                files={"file": ("MyArea.zip", b"mydata", "application/zip")},
                data={"areaId": "my-area"},
                headers={"Authorization": "Bearer test_token"},
            )

            # Get own areas
            response = await client.get(
                "/ca/areas",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["areas"]) == 1
        assert data["areas"][0]["areaId"] == "my-area"
        # Should NOT contain competentAuthorityId/Name (CA knows who it is)
        assert "competentAuthorityId" not in data["areas"][0]
        assert "competentAuthorityName" not in data["areas"][0]
        # Should NOT contain endedAt
        assert "endedAt" not in data["areas"][0]

    async def test_get_own_areas_does_not_return_other_ca_areas(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test that GET /ca/areas does NOT return areas from other CAs."""
        from tests.fixtures.factories import AreaFactory

        # Create area for another CA directly
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="9999",
            competent_authority_name="Other Authority",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["areas"] == []  # CA "0363" has no areas

    async def test_get_own_areas_forbidden_missing_read_role(
        self, async_session: AsyncSession
    ):
        """Test GET /ca/areas with missing sdep_read role."""

        def mock_token_without_read_role():
            return {
                "sub": "test_user",
                "client_id": "0363",
                "client_name": "Gemeente Amsterdam",
                "realm_access": {
                    "roles": ["sdep_ca", "sdep_write"]
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
                "/ca/areas",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # Tests for GET /ca/areas/count

    async def test_count_own_areas_empty(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/areas/count returns 0 when no areas exist."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0

    async def test_count_own_areas_returns_correct_count(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test GET /ca/areas/count returns correct count after creating areas."""
        import asyncio

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Create two areas for this CA
            await client.post(
                "/ca/areas",
                files={"file": ("Area1.zip", b"data1", "application/zip")},
                data={"areaId": "count-area-1"},
                headers={"Authorization": "Bearer test_token"},
            )

            # Wait to ensure different timestamp (SQLite second precision)
            await asyncio.sleep(1.0)

            await client.post(
                "/ca/areas",
                files={"file": ("Area2.zip", b"data2", "application/zip")},
                data={"areaId": "count-area-2"},
                headers={"Authorization": "Bearer test_token"},
            )

            # Count own areas
            response = await client.get(
                "/ca/areas/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2

    # Tests for DELETE /ca/areas/{areaId}

    async def test_delete_area_success(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test DELETE /ca/areas/{areaId} soft-deletes the area (204)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            # Create an area first
            post_response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                data={"areaId": "delete-test-area"},
                headers={"Authorization": "Bearer test_token"},
            )
            assert post_response.status_code == status.HTTP_201_CREATED

            # Delete the area
            delete_response = await client.delete(
                "/ca/areas/delete-test-area",
                headers={"Authorization": "Bearer test_token"},
            )
            assert delete_response.status_code == status.HTTP_204_NO_CONTENT

            # Verify the area is gone from GET
            get_response = await client.get(
                "/ca/areas",
                headers={"Authorization": "Bearer test_token"},
            )
            assert get_response.status_code == status.HTTP_200_OK
            assert get_response.json()["areas"] == []

    async def test_delete_area_not_found(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test DELETE /ca/areas/{areaId} for nonexistent area returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/ca/areas/nonexistent-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_area_forbidden_missing_write_role(
        self, async_session: AsyncSession
    ):
        """Test DELETE /ca/areas/{areaId} with missing sdep_write role returns 403."""

        def mock_token_without_write_role():
            return {
                "sub": "test_user",
                "client_id": "0363",
                "client_name": "Gemeente Amsterdam",
                "realm_access": {
                    "roles": ["sdep_ca", "sdep_read"]
                },  # Missing sdep_write
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_token_without_write_role

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/ca/areas/some-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "sdep_write" in response.json()["detail"][0]["msg"]

    async def test_delete_area_unauthorized_no_token(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Test DELETE /ca/areas/{areaId} without authentication token returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/ca/areas/some-area",
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_delete_area_invalid_area_id_pattern(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test DELETE /ca/areas/{areaId} with invalid areaId pattern returns 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/ca/areas/INVALID_ID",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_delete_area_other_ca(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test DELETE /ca/areas/{areaId} for area from different CA returns 404."""
        from tests.fixtures.factories import AreaFactory

        # Create area for another CA directly
        await AreaFactory.create_async(
            async_session,
            area_id="other-ca-area",
            competent_authority_id="9999",
            competent_authority_name="Other Authority",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/ca/areas/other-ca-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_count_own_areas_does_not_count_other_ca_areas(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Test that GET /ca/areas/count does NOT count areas from other CAs."""
        from tests.fixtures.factories import AreaFactory

        # Create area for another CA directly
        await AreaFactory.create_async(
            async_session,
            competent_authority_id="9999",
            competent_authority_name="Other Authority",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0  # CA "0363" has no areas
