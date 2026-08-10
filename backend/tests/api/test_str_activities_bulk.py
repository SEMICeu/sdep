"""Tests for STR Bulk Activities API endpoint."""

from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.str.v1 import app_str_v1
from app.db.config import get_async_db, get_async_db_read_only
from app.enums import ActivityStatus
from app.models.competent_authority import CompetentAuthority
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
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
            "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
        },
        "temporal": {
            "startDatetime": "2025-06-01T14:00:00Z",
            "endDatetime": "2025-06-07T11:00:00Z",
        },
        "numberOfGuests": 2,
        "countryOfGuests": ["NLD", "NLD"],
    }
    base.update(overrides)
    return base


@pytest.mark.database
class TestSTRActivitiesBulkAPI:
    """Test suite for POST /str/activities/bulk API endpoint."""

    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        """Setup dependency overrides for authenticated tests."""
        app_str_v1.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db
        app_str_v1.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

        app_str_v1.dependency_overrides.clear()

    @pytest.fixture
    def setup_db_only(self, async_session: AsyncSession):
        """Setup database override only (no auth override)."""

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db
        app_str_v1.dependency_overrides[get_async_db_read_only] = override_get_db

        yield

        app_str_v1.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def test_areas(self, async_session: AsyncSession):
        """Create test areas for bulk activities tests."""
        from app.crud import area as area_crud

        result = await async_session.execute(
            select(CompetentAuthority).where(
                CompetentAuthority.competent_authority_id == "test",
                CompetentAuthority.ended_at.is_(None),
            )
        )
        ca = result.scalar_one_or_none()
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

        return {"area1": areas["area1"], "area2": areas["area2"], "ca": ca}

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self, async_session: AsyncSession):
        """Setup fixture for test isolation."""
        yield

    # ── Success cases ────────────────────────────────────────────────────

    async def test_bulk_all_valid_201(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """All items valid → 201 + all OK with embedded activity."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
            assert "activity" in item
            assert item["activity"]["activityId"] is not None
            assert item["activity"]["status"] == "finished"
            assert item["activity"]["createdAt"] is not None
            assert "errors" not in item

    async def test_bulk_ok_item_has_embedded_activity_fields(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """OK item embedded activity contains all expected fields."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "fields-001",
                            activityId="my-id-001",
                            activityName="Test Activity",
                            numberOfGuests=3,
                            countryOfGuests=["NLD", "DEU", "BEL"],
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        result = data["results"][0]
        activity = result["activity"]

        # Result-level activityId is the client-supplied ID
        assert result["activityId"] == "my-id-001"

        # Embedded activity fields
        assert activity["activityId"] == "my-id-001"
        assert activity["activityName"] == "Test Activity"
        assert activity["status"] == "finished"
        assert activity["areaId"] == test_areas["area1"].area_id
        assert activity["areaName"] == test_areas["area1"].area_name
        assert activity["competentAuthorityId"] == "test"
        assert activity["competentAuthorityName"] == "Test Authority"
        assert activity["url"] == "http://example.com/bulk-fields-001"
        assert activity["registrationNumber"] == "REG-fields-001"
        assert activity["address"]["thoroughfare"] == "Turfmarkt"
        assert activity["address"]["locatorDesignatorNumber"] == 147
        assert activity["address"]["postCode"] == "2500EA"
        assert activity["address"]["postName"] == "Den Haag"
        assert activity["address"]["fullAddress"] == "Turfmarkt 147, 2500EA Den Haag"
        assert activity["numberOfGuests"] == 3
        assert activity["countryOfGuests"] == ["NLD", "DEU", "BEL"]
        assert activity["temporal"]["startDatetime"] == "2025-06-01T14:00:00Z"
        assert activity["temporal"]["endDatetime"] == "2025-06-07T11:00:00Z"
        UUID(activity["platformId"])
        assert activity["platformId"] != "str01"
        assert activity["platformName"] == "STR Platform 01"
        assert activity["createdAt"] is not None

    async def test_bulk_ok_item_without_activity_id_has_null_result_level_id(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """OK item without client-supplied activityId → result-level activityId is null, embedded has generated UUID."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "noid-001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        result = data["results"][0]

        # Result-level activityId is null (client didn't supply one)
        assert result["activityId"] is None
        # Embedded activity has a generated UUID
        assert result["activity"]["activityId"] is not None
        assert result["activity"]["status"] == "finished"
        assert len(result["activity"]["activityId"]) > 0

    async def test_bulk_ok_item_with_activity_id_has_matching_result_level_id(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """OK item with client-supplied activityId → result-level activityId matches embedded."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "withid-001",
                            activityId="supplied-id-123",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        result = data["results"][0]

        assert result["activityId"] == "supplied-id-123"
        assert result["activity"]["activityId"] == "supplied-id-123"
        assert result["activity"]["status"] == "finished"

    async def test_bulk_accepts_explicit_cancelled_status(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Explicit cancelled lifecycle status is accepted and returned."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "cancelled-001",
                            activityId="cancelled-id-001",
                            status="cancelled",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()["results"][0]
        assert result["status"] == "OK"
        assert result["activity"]["status"] == "cancelled"

    async def test_bulk_ok_without_locator_designator_number(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Address.locatorDesignatorNumber is optional → item accepted, field is null in response."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        {
                            "areaId": test_areas["area1"].area_id,
                            "url": "http://example.com/bulk-no-number",
                            "registrationNumber": "REG-no-number",
                            "address": {
                                "thoroughfare": "Turfmarkt",
                                "postCode": "2500EA",
                                "postName": "Den Haag",
                                "fullAddress": "Turfmarkt, 2500EA Den Haag",
                            },
                            "temporal": {
                                "startDatetime": "2025-06-01T14:00:00Z",
                                "endDatetime": "2025-06-07T11:00:00Z",
                            },
                            "numberOfGuests": 2,
                            "countryOfGuests": ["NLD", "NLD"],
                        },
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        activity = data["results"][0]["activity"]
        assert activity["address"]["thoroughfare"] == "Turfmarkt"
        assert activity["address"]["locatorDesignatorNumber"] is None
        assert activity["status"] == "finished"

    # ── Failure cases ────────────────────────────────────────────────────

    async def test_bulk_all_invalid_422(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """All items invalid (bad area) → 422 + all NOK with errorMessages array."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
            assert isinstance(item["errors"]["detail"], list)
            assert any("not found" in d["msg"] for d in item["errors"]["detail"])
            assert "activity" not in item

    async def test_bulk_nok_item_has_no_activity(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """NOK item has no embedded activity object."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity("nonexistent-area", "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        data = response.json()
        result = data["results"][0]
        assert result["status"] == "NOK"
        assert "activity" not in result
        assert "errors" in result

    # ── Partial success ──────────────────────────────────────────────────

    async def test_bulk_partial_success_200(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Mixed valid/invalid → 200 + mixed OK/NOK."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
        assert "activity" in data["results"][0]
        assert data["results"][1]["status"] == "NOK"
        assert "activity" not in data["results"][1]
        assert data["results"][2]["status"] == "OK"
        assert "activity" in data["results"][2]

    # ── Per-item Pydantic validation ─────────────────────────────────────

    async def test_bulk_pydantic_failure_per_item(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Pydantic validation failure (missing required field) → NOK for that item only."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
        assert isinstance(data["results"][1]["errors"]["detail"], list)
        assert (
            len(data["results"][1]["errors"]["detail"]) > 1
        )  # Multiple missing fields
        assert data["results"][2]["status"] == "OK"

    # ── Empty list ───────────────────────────────────────────────────────

    async def test_bulk_empty_list_422(
        self, async_session: AsyncSession, setup_overrides
    ):
        """Empty list → 422 (Pydantic min_length=1)."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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

        app_str_v1.dependency_overrides[verify_bearer_token] = mock_no_str_role

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        app_str_v1.dependency_overrides.clear()

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

        app_str_v1.dependency_overrides[verify_bearer_token] = mock_no_write_role

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "sdep_write" in str(response.json()["detail"]).lower()
        app_str_v1.dependency_overrides.clear()

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

        app_str_v1.dependency_overrides[verify_bearer_token] = mock_without_client_id

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "client_id" in str(response.json()["detail"]).lower()
        app_str_v1.dependency_overrides.clear()

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

        app_str_v1.dependency_overrides[verify_bearer_token] = mock_without_client_name

        async def override_get_db():
            yield async_session

        app_str_v1.dependency_overrides[get_async_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "b001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "client_name" in str(response.json()["detail"]).lower()
        app_str_v1.dependency_overrides.clear()

    # ── Intra-batch duplicates (last-wins) ───────────────────────────────

    async def test_bulk_intra_batch_duplicates_last_wins(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Same activityId at index 0 and 2 → index 0 NOK (superseded), index 2 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
        assert any(
            "Superseded" in d["msg"] for d in data["results"][0]["errors"]["detail"]
        )
        assert any(
            "index 2" in d["msg"] for d in data["results"][0]["errors"]["detail"]
        )
        # Index 1 OK (different ID)
        assert data["results"][1]["status"] == "OK"
        # Index 2 OK (last occurrence wins)
        assert data["results"][2]["status"] == "OK"
        assert data["results"][2]["activityId"] == "duplicate-id"

    # ── Activity versioning in bulk ──────────────────────────────────────

    async def test_bulk_versioning_marks_existing_as_ended(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Resubmitting with cancelled creates a new cancelled current version."""
        import asyncio

        from app.crud import activity as activity_crud

        # First: create an activity via bulk
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "ver-v1",
                            activityId="versioned-bulk",
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )
        assert response1.status_code == status.HTTP_201_CREATED

        # Wait to ensure different timestamp (SQLite second precision)
        await asyncio.sleep(1.0)

        # Now submit via bulk with same activityId
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response2 = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "ver-v2",
                            activityId="versioned-bulk",
                            status="cancelled",
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
        assert data["results"][0]["activity"]["status"] == "cancelled"

        current = await activity_crud.get_by_activity_id(
            async_session, "versioned-bulk"
        )
        assert current is not None
        assert current.status == ActivityStatus.cancelled

        versions = [
            record
            for record in await activity_crud.get_all(async_session)
            if record.activity_id == "versioned-bulk"
        ]
        assert len(versions) == 2
        assert sum(1 for record in versions if record.ended_at is None) == 1
        assert sum(1 for record in versions if record.ended_at is not None) == 1

    # ── Platform resolution ──────────────────────────────────────────────

    async def test_bulk_platform_no_version_when_name_unchanged(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Same platform name → no new version; activity still created."""
        from app.crud import platform as platform_crud

        # First call creates the platform
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/activities/bulk",
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
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response2 = await client.post(
                "/activities/bulk",
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
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
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
        assert data["results"][0]["activity"]["activityId"] == "my-custom-id-001"

    async def test_bulk_without_activity_ids_auto_generated(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Activities without activityId get auto-generated UUIDs in embedded activity."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(test_areas["area1"].area_id, "auto-001"),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Result-level activityId is null (not supplied by client)
        assert data["results"][0]["activityId"] is None
        # Embedded activity has generated UUID
        activity_id = data["results"][0]["activity"]["activityId"]
        assert activity_id is not None
        assert len(activity_id) > 0

    # ── Guest field constraints ──────────────────────────────────────────

    async def test_bulk_rejects_missing_number_of_guests(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """numberOfGuests is required → 422 with loc=numberOfGuests."""
        item = _make_activity(test_areas["area1"].area_id, "missing-nog-001")
        del item["numberOfGuests"]
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={"activities": [item]},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        result = response.json()["results"][0]
        assert result["status"] == "NOK"
        locs = [tuple(err["loc"] or []) for err in result["errors"]["detail"]]
        assert any("numberOfGuests" in loc for loc in locs)

    async def test_bulk_rejects_missing_country_of_guests(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """countryOfGuests is required → 422 with loc=countryOfGuests."""
        item = _make_activity(test_areas["area1"].area_id, "missing-cog-001")
        del item["countryOfGuests"]
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={"activities": [item]},
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        result = response.json()["results"][0]
        assert result["status"] == "NOK"
        locs = [tuple(err["loc"] or []) for err in result["errors"]["detail"]]
        assert any("countryOfGuests" in loc for loc in locs)

    async def test_bulk_rejects_guest_cardinality_mismatch(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """numberOfGuests must equal len(countryOfGuests) → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "card-001",
                            numberOfGuests=3,
                            countryOfGuests=["NLD", "NLD"],
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        result = response.json()["results"][0]
        assert result["status"] == "NOK"
        msgs = " ".join(err["msg"] for err in result["errors"]["detail"])
        assert "numberOfGuests" in msgs or "countryOfGuests" in msgs

    async def test_bulk_accepts_na_country_code(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """'N/A' is a valid element of countryOfGuests → 201."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "na-001",
                            numberOfGuests=2,
                            countryOfGuests=["NLD", "N/A"],
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        activity = response.json()["results"][0]["activity"]
        assert activity["countryOfGuests"] == ["NLD", "N/A"]

    async def test_bulk_rejects_lowercase_na_country_code(
        self, async_session: AsyncSession, setup_overrides, test_areas
    ):
        """Lowercase 'n/a' is rejected (uppercase only) → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_str_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities/bulk",
                json={
                    "activities": [
                        _make_activity(
                            test_areas["area1"].area_id,
                            "na-lc-001",
                            numberOfGuests=1,
                            countryOfGuests=["n/a"],
                        ),
                    ]
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["results"][0]["status"] == "NOK"
