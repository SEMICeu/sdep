"""Tests for JWT client_id functional ID validation.

Validates that all endpoints reject invalid client_id claims (used as
platform_id or competent_authority_id) that do not match the functional ID
pattern: ^[A-Za-z0-9-]+$ (1-64 chars).
"""

from typing import Any

import pytest
from app.api.v0.main import app_v0
from app.api.v0.security import verify_bearer_token
from app.db.config import get_async_db, get_async_db_read_only
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# --- Invalid client_id values ---

INVALID_CLIENT_IDS = [
    pytest.param("has spaces", id="spaces"),
    pytest.param("under_score", id="underscore"),
    pytest.param("special!char", id="special-char"),
    pytest.param("dot.separated", id="dot"),
    pytest.param("slash/path", id="slash"),
    pytest.param("a" * 65, id="too-long-65-chars"),
]


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
        app_v0.dependency_overrides.clear()

    def _setup(self, async_session: AsyncSession, client_id: str):
        """Setup dependency overrides with an invalid client_id."""
        app_v0.dependency_overrides[verify_bearer_token] = lambda: _make_ca_token(
            client_id
        )

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db
        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_post_area_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """POST /ca/areas returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ca/areas",
                files={"file": ("Area.zip", b"zipdata", "application/zip")},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_get_own_areas_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /ca/areas returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_count_own_areas_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /ca/areas/count returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas/count",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_get_own_area_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /ca/areas/{areaId} returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/areas/some-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_delete_area_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """DELETE /ca/areas/{areaId} returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.delete(
                "/ca/areas/some-area",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_get_ca_activities_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /ca/activities returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/activities",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_count_ca_activities_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """GET /ca/activities/count returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.get(
                "/ca/activities/count",
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
        app_v0.dependency_overrides.clear()

    def _setup(self, async_session: AsyncSession, client_id: str):
        """Setup dependency overrides with an invalid client_id."""
        app_v0.dependency_overrides[verify_bearer_token] = lambda: _make_str_token(
            client_id
        )

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db
        app_v0.dependency_overrides[get_async_db_read_only] = override_get_db

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_post_activity_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """POST /str/activities returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities",
                json={
                    "areaId": "some-area",
                    "url": "http://example.com/test",
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
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in response.json()["detail"][0]["msg"]

    @pytest.mark.parametrize("invalid_id", INVALID_CLIENT_IDS)
    async def test_post_activities_bulk_rejects_invalid_client_id(
        self, async_session: AsyncSession, invalid_id: str
    ):
        """POST /str/activities/bulk returns 422 when JWT client_id is invalid."""
        self._setup(async_session, invalid_id)

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
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
        app_v0.dependency_overrides.clear()

    @pytest.mark.parametrize(
        "valid_id",
        [
            pytest.param("0363", id="numeric"),
            pytest.param("sdep-ca0363", id="lowercase-with-hyphens"),
            pytest.param("SDEP-CA0363", id="uppercase-with-hyphens"),
            pytest.param("MixedCase-Id-123", id="mixed-case"),
            pytest.param("a", id="single-char"),
            pytest.param("a" * 64, id="max-length-64-chars"),
        ],
    )
    async def test_post_area_accepts_valid_client_id(
        self, async_session: AsyncSession, valid_id: str
    ):
        """POST /ca/areas accepts valid client_id values."""
        app_v0.dependency_overrides[verify_bearer_token] = lambda: {
            "sub": "test_user",
            "client_id": valid_id,
            "client_name": "Test Authority",
            "realm_access": {"roles": ["sdep_ca", "sdep_read", "sdep_write"]},
        }

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

        assert response.status_code == status.HTTP_201_CREATED
