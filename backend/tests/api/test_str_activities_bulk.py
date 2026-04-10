"""Tests for STR Bulk Activities API endpoint."""

from typing import Any

import pytest
import pytest_asyncio
from app.api.v0.main import app_v0
from app.api.v0.security import verify_bearer_token
from app.db.config import get_async_db, get_async_db_read_only
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


def _make_activity(area_id: str, suffix: str = "001", **overrides) -> dict:
    """Helper to create a valid activity dict for bulk requests."""
    base = {
        "areaId": area_id,
        "url": f"http://example.com/bulk-{suffix}",
        "registrationNumber": f"REG-{suffix}",
        "address": {
            "thoroughfare": "Turfmarkt",
            "locatorDesignatorNumber": 147,
            "postCode": "2500EA",
            "postName": "Den Haag",
        },
        "temporal": {
            "startDatetime": "2025-06-01T14:00:00Z",
            "endDatetime": "2025-06-07T11:00:00Z",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.database
class TestSTRActivitiesBulkAPI:
    """Test suite for POST /str/activities/bulk API endpoint."""

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
        """Create test areas for bulk activities tests."""
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
            ("area1", "550e8400-e29b-41d4-a716-446655440001"),
            ("area2", "550e8400-e29b-41d4-a716-446655440002"),
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
    async def cleanup(self, async_session: AsyncSession):
        """Setup fixture for test isolation."""
        yield

    # ── Success cases ────────────────────────────────────────────────────

    async def test_bulk_all_valid_201(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """All items valid → 201 + all OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                        _make_activity(test_areas["area2"].area_id, "b002"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["totalReceived"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2
        for item in data["results"]:
            assert item["status"] == "OK"
            assert item["activityId"] is not None
            assert item.get("errorMessage") is None

    # ── Failure cases ────────────────────────────────────────────────────

    async def test_bulk_all_invalid_422(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """All items invalid (bad area) → 422 + all NOK."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity("nonexistent-area-1", "b001"),
                        _make_activity("nonexistent-area-2", "b002"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        assert data["totalReceived"] == 2
        assert data["succeeded"] == 0
        assert data["failed"] == 2
        for item in data["results"]:
            assert item["status"] == "NOK"
            assert "not found" in item["errorMessage"]

    # ── Partial success ──────────────────────────────────────────────────

    async def test_bulk_partial_success_200(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Mixed valid/invalid → 200 + mixed OK/NOK."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                        _make_activity("nonexistent-area", "b002"),
                        _make_activity(test_areas["area2"].area_id, "b003"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["totalReceived"] == 3
        assert data["succeeded"] == 2
        assert data["failed"] == 1
        assert data["results"][0]["status"] == "OK"
        assert data["results"][1]["status"] == "NOK"
        assert data["results"][2]["status"] == "OK"

    # ── Per-item Pydantic validation ─────────────────────────────────────

    async def test_bulk_pydantic_failure_per_item(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Pydantic validation failure (missing required field) → NOK for that item only."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                        {
                            # Missing registrationNumber, url, address, temporal
                            "areaId": test_areas["area1"].area_id,
                        },
                        _make_activity(test_areas["area2"].area_id, "b003"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["succeeded"] == 2
        assert data["failed"] == 1
        assert data["results"][0]["status"] == "OK"
        assert data["results"][1]["status"] == "NOK"
        assert data["results"][2]["status"] == "OK"

    # ── Empty list ───────────────────────────────────────────────────────

    async def test_bulk_empty_list_422(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Empty list → 422 (Pydantic min_length=1)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={"activities": []},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ── Auth ─────────────────────────────────────────────────────────────

    async def test_bulk_without_authentication_401(
        self, async_session: AsyncSession, setup_db_only
    ):
        """Missing token → 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={"activities": [{"areaId": "test"}]},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_bulk_without_str_role_403(
        self, async_session: AsyncSession, test_areas
    ):
        """Wrong role → 403."""

        def mock_no_str_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "ca01",
                "client_name": "CA 01",
                "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_no_str_role

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        app_v0.dependency_overrides.clear()

    async def test_bulk_without_write_role_403(
        self, async_session: AsyncSession, test_areas
    ):
        """Missing write role -> 403."""

        def mock_no_write_role() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "str01",
                "client_name": "STR Platform 01",
                "realm_access": {"roles": ["sdep_str", "sdep_read"]},
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_no_write_role

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "sdep_write" in str(response.json()["detail"]).lower()
        app_v0.dependency_overrides.clear()

    async def test_bulk_without_client_id_claim_401(
        self, async_session: AsyncSession, test_areas
    ):
        """Missing client_id claim -> 401."""

        def mock_without_client_id() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_name": "STR Platform 01",
                "realm_access": {"roles": ["sdep_str", "sdep_read", "sdep_write"]},
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_without_client_id

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "client_id" in str(response.json()["detail"]).lower()
        app_v0.dependency_overrides.clear()

    async def test_bulk_without_client_name_claim_401(
        self, async_session: AsyncSession, test_areas
    ):
        """Missing client_name claim -> 401."""

        def mock_without_client_name() -> dict[str, Any]:
            return {
                "sub": "test_user",
                "client_id": "str01",
                "realm_access": {"roles": ["sdep_str", "sdep_read", "sdep_write"]},
            }

        app_v0.dependency_overrides[verify_bearer_token] = mock_without_client_name

        async def override_get_db():
            yield async_session

        app_v0.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "client_name" in str(response.json()["detail"]).lower()
        app_v0.dependency_overrides.clear()

    # ── Intra-batch duplicates (last-wins) ───────────────────────────────

    async def test_bulk_intra_batch_duplicates_last_wins(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Same activityId at index 0 and 2 → index 0 NOK (superseded), index 2 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "dup-v1",
                            activityId="duplicate-id",
                        ),
                        _make_activity(test_areas["area2"].area_id, "other"),
                        _make_activity(
                            test_areas["area1"].area_id,
                            "dup-v2",
                            activityId="duplicate-id",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["succeeded"] == 2
        assert data["failed"] == 1
        # Index 0 superseded
        assert data["results"][0]["status"] == "NOK"
        assert "Superseded" in data["results"][0]["errorMessage"]
        assert "index 2" in data["results"][0]["errorMessage"]
        # Index 1 OK (different ID)
        assert data["results"][1]["status"] == "OK"
        # Index 2 OK (last occurrence wins)
        assert data["results"][2]["status"] == "OK"
        assert data["results"][2]["activityId"] == "duplicate-id"

    # ── Activity versioning in bulk ──────────────────────────────────────

    async def test_bulk_versioning_marks_existing_as_ended(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """activityId exists in DB → old version marked as ended, new version created."""
        import asyncio

        # First: create an activity via single endpoint
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/str/activities",
                json=_make_activity(
                    test_areas["area1"].area_id,
                    "ver-v1",
                    activityId="versioned-bulk",
                ),
                headers={"Authorization": "Bearer test_token"},
            )
        assert response1.status_code == status.HTTP_201_CREATED

        # Wait to ensure different timestamp (SQLite second precision)
        await asyncio.sleep(1.0)

        # Now submit via bulk with same activityId
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response2 = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "ver-v2",
                            activityId="versioned-bulk",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response2.status_code == status.HTTP_201_CREATED
        data = response2.json()
        assert data["succeeded"] == 1
        assert data["results"][0]["activityId"] == "versioned-bulk"
        assert data["results"][0]["status"] == "OK"

    # ── Platform resolution ──────────────────────────────────────────────

    async def test_bulk_platform_no_version_when_name_unchanged(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Same platform name → no new version; activity still created."""
        from app.crud import platform as platform_crud

        # First call creates the platform
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "plat-001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )
        assert response1.status_code == status.HTTP_201_CREATED

        # Count platform versions
        platforms = await platform_crud.get_all(async_session)
        platform_count_before = len([p for p in platforms if p.platform_id == "str01"])

        # Second call with same name should NOT create new platform version
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response2 = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "plat-002"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )
        assert response2.status_code == status.HTTP_201_CREATED

        platforms_after = await platform_crud.get_all(async_session)
        platform_count_after = len(
            [p for p in platforms_after if p.platform_id == "str01"]
        )
        assert platform_count_after == platform_count_before

    # ── Response structure ───────────────────────────────────────────────

    async def test_bulk_response_preserves_order(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Results array preserves original request order."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "ord-001",
                            activityId="first",
                        ),
                        _make_activity("bad-area", "ord-002", activityId="second"),
                        _make_activity(
                            test_areas["area2"].area_id,
                            "ord-003",
                            activityId="third",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        data = response.json()
        assert data["results"][0]["activityIndex"] == 0
        assert data["results"][0]["activityId"] == "first"
        assert data["results"][1]["activityIndex"] == 1
        assert data["results"][1]["activityId"] == "second"
        assert data["results"][2]["activityIndex"] == 2
        assert data["results"][2]["activityId"] == "third"

    async def test_bulk_with_activity_ids(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Activities with explicit activityId are created with that ID."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "custom-001",
                            activityId="my-custom-id-001",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["results"][0]["activityId"] == "my-custom-id-001"

    async def test_bulk_without_activity_ids_auto_generated(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Activities without activityId get auto-generated UUIDs."""
        async with AsyncClient(
            transport=ASGITransport(app=app_v0), base_url="http://test"
        ) as client:
            response = await client.post(
                "/str/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "auto-001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        activity_id = data["results"][0]["activityId"]
        assert activity_id is not None
        assert len(activity_id) > 0
