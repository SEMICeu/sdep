"""Tests for JWT client_id functional ID validation.

Validates that all endpoints reject invalid client_id claims.
"""

from typing import Any

import pytest
from app.api.common.routers import ca_areas
from app.api.common.security import verify_bearer_token
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.str.v1 import app_str_v1
from app.db.config import get_async_db, get_async_db_read_only
from app.security.malware_scan import ScanResult
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.zip_stub import ZIP

# --- Invalid client_id values ---

INVALID_CLIENT_IDS = [
    pytest.param("has spaces", id="spaces"),
    pytest.param("special!char", id="special-char"),
    pytest.param("slash/path", id="slash"),
    pytest.param("a" * 65, id="too-long-65-chars"),
]


@pytest.fixture(autouse=True)
def mock_malware_scan(monkeypatch):
    """Keep API tests independent from the real ClamAV daemon."""

    async def clean_scan(filedata: bytes) -> ScanResult:
        return ScanResult(
            passed_malware_scan=True,
            message="mocked clean file",
        )

    monkeypatch.setattr(
        ca_areas,
        "scan_file_for_malware",
        clean_scan,
    )


def _make_ca_token(client_id: str) -> dict[str, Any]:
    """Create a CA token payload with the given client_id."""
    return {
        "sub": "test_user",
        "client_id": client_id,
        "client_name": "Test Authority",
        "realm_access": {"roles": ["sdep_ca", "sdep_read", "sdep_write"]},
    }


def _make_str_token(client_id: str) -> dict[str, Any]:
    """Create an STR token payload with the given client_id."""
    return {
        "sub": "test_user",
        "client_id": client_id,
        "client_name": "Test Platform",
        "realm_access": {"roles": ["sdep_str", "sdep_read", "sdep_write"]},
    }


@pytest.mark.database
class TestInvalidCAClientId:
    """Test that CA endpoints reject invalid client_id from JWT."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up dependency overrides after each test."""
        yield
        app_ca_v1.dependency_overrides.clear()

    def _setup(self, async_session: AsyncSession, client_id: str):
        """Setup dependency overrides with an invalid client_id."""
        app_ca_v1.dependency_overrides[verify_bearer_token] = lambda: _make_ca_token(
            client_id
        )

        async def override_get_db():
            yield async_session

        app_ca_v1.dependency_overrides[get_async_db] = override_get_db
        app_ca_v1.dependency_overrides[get_async_db_read_only] = override_get_db

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_post_area_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """POST /areas returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/areas",
                files={"file": ("Area.zip", ZIP, "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_get_own_areas_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /areas returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/areas",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_count_own_areas_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /areas/count returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/areas/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_get_own_area_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /areas/{areaId} returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/areas/some-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_delete_area_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """DELETE /areas/{areaId} returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/areas/some-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_get_ca_activities_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /activities returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_count_ca_activities_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /activities/count returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.get(
                "/activities/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]


@pytest.mark.database
class TestInvalidSTRClientId:
    """Test that STR endpoints reject invalid client_id from JWT."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up dependency overrides after each test."""
        yield
        app_str_v1.dependency_overrides.clear()

    def _setup(self, async_session: AsyncSession, client_id: str):
        """Setup dependency overrides with an invalid client_id."""
        app_str_v1.dependency_overrides[verify_bearer_token] = lambda: _make_str_token(
            client_id
        )

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db
        app_str_v1.dependency_overrides[get_async_db_read_only] = override_get_db

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_post_activities_bulk_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """POST /activities/bulk returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        {
                            "areaId": "some-area",
                            "url": "http://example.com/bulk",
                            "registrationNumber": "REG001",
                            "address": {
                                "thoroughfare": "Prinsengracht",
                                "locatorDesignatorNumber": 263,
                                "postCode": "1016GV",
                                "postName": "Amsterdam",
                            },
                            "temporal": {
                                "startDatetime": "2025-06-01T14:00:00Z",
                                "endDatetime": "2025-06-07T11:00:00Z",
                            },
                        }
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]


@pytest.mark.database
class TestValidClientIdAccepted:
    """Verify that valid client_id values (edge cases) are accepted."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up dependency overrides after each test."""
        yield
        app_ca_v1.dependency_overrides.clear()

    @pytest.mark.parametrize(
        "valid_id",
        [
            pytest.param("0363", id="numeric"),
            pytest.param("sdep-ca.0363", id="lowercase-with-dot"),
            pytest.param("SDEP-CA0363", id="uppercase-with-hyphens"),
            pytest.param("MixedCase-Id-123", id="mixed-case"),
            pytest.param("client.with.dot", id="dot-separated"),
            pytest.param("client_with_underscore", id="underscore-separated"),
            pytest.param("a", id="single-char"),
            pytest.param("a" * 64, id="max-length-64-chars"),
        ],
    )
    async def test_post_area_accepts_valid_client_id(
        self, async_session: AsyncSession, valid_id: str
    ):
        """POST /areas accepts valid client_id values."""
        app_ca_v1.dependency_overrides[verify_bearer_token] = lambda: {
            "sub": "test_user",
            "client_id": valid_id,
            "client_name": "Test Authority",
            "realm_access": {"roles": ["sdep_ca", "sdep_read", "sdep_write"]},
        }

        async def override_get_db():
            yield async_session

        app_ca_v1.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_ca_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/areas",
                files={"file": ("Area.zip", ZIP, "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
