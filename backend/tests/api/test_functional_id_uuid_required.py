"""Tests for the UUID format check on a new, supplied functional ID.

Through the real sub-apps: POST areas (CA v1), POST activities (STR v1) and POST
listings (STR v2). The suite runs with FUNCTIONAL_ID_UUID_REQUIRED off (see
pyproject.toml), so these tests switch it on.
"""

import asyncio
from typing import Any

import pytest
from app.api.common.security import verify_bearer_token
from app.api.domains.ca.routers import areas as ca_areas
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.str.v1 import app_str_v1
from app.api.domains.str.v2 import app_str_v2
from app.config import Settings, settings
from app.db.config import get_async_db, get_async_db_read_only
from app.models.identity import AreaIdentity
from app.security.malware_scan import ScanResult
from app.services import functional_id
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.zip_stub import ZIP, zip_named
from tests.fixtures.factories import AreaFactory, CompetentAuthorityFactory

LOWER = "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"
UPPER = LOWER.upper()
APPS = (app_ca_v1, app_str_v1, app_str_v2)

ADDRESS = {
    "thoroughfare": "Turfmarkt",
    "locatorDesignatorNumber": 147,
    "postCode": "2500EA",
    "postName": "Den Haag",
    "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
}


def _token(role: str, client_id: str, name: str):
    def mock() -> dict[str, Any]:
        return {
            "sub": client_id,
            "client_id": client_id,
            "client_name": name,
            "realm_access": {"roles": [role, "sdep_read", "sdep_write"]},
        }

    return mock


TOKENS = {
    app_ca_v1: _token("sdep_ca", "0363", "Gemeente Amsterdam"),
    app_str_v1: _token("sdep_str", "str01", "STR Platform 01"),
    app_str_v2: _token("sdep_str", "str01", "STR Platform 01"),
}


def _activity(area_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "areaId": area_id,
        "url": "http://example.com/activity",
        "registrationNumber": "REG-1",
        "address": ADDRESS,
        "temporal": {
            "startDatetime": "2025-06-01T14:00:00Z",
            "endDatetime": "2025-06-07T11:00:00Z",
        },
        "numberOfGuests": 2,
        "countryOfGuests": ["NLD", "NLD"],
    }
    base.update(overrides)
    return base


def _listing(area_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "areaId": area_id,
        "url": "http://example.com/listing",
        "address": ADDRESS,
        "declaredAsShortTermRental": True,
    }
    base.update(overrides)
    return base


# Per bulk endpoint: app, path, list key, ID field, result key, item builder
BULK = {
    "activity": (
        app_str_v1,
        "/activities/bulk",
        "activities",
        "activityId",
        "activity",
        _activity,
    ),
    "listing": (
        app_str_v2,
        "/listings/bulk",
        "listings",
        "listingId",
        "listing",
        _listing,
    ),
}


async def _post_area(area_id: str | None, tag: str = "") -> Any:
    async with AsyncClient(
        transport=ASGITransport(app=app_ca_v1), base_url="http://test"
    ) as client:
        return await client.post(
            "/areas",
            files={"file": ("Area.zip", zip_named(tag) if tag else ZIP)},
            data={} if area_id is None else {"areaId": area_id},
            headers={"Authorization": "Bearer t"},
        )


async def _post_bulk(kind: str, area_id: str, **overrides: Any) -> Any:
    app, path, list_key, _id_field, _result_key, build = BULK[kind]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            path,
            json={list_key: [build(area_id, **overrides)]},
            headers={"Authorization": "Bearer t"},
        )


class TestUuidPattern:
    @pytest.mark.parametrize(
        "value",
        [LOWER, "00000000-0000-0000-0000-000000000000"],
        ids=["v4", "nil"],
    )
    def test_lowercase_uuid_matches(self, value: str) -> None:
        assert functional_id.is_uuid(value)

    @pytest.mark.parametrize(
        "value",
        [
            UPPER,
            LOWER.replace("-", ""),
            LOWER[:-1],
            LOWER + "0",
            LOWER.replace("3f2a", "3g2a"),
            f"{{{LOWER}}}",
            f"{LOWER}\n",
            "amsterdam-area0363",
        ],
        ids=[
            "uppercase",
            "no-hyphens",
            "too-short",
            "too-long",
            "no-hex",
            "braces",
            "trailing-newline",
            "own-id",
        ],
    )
    def test_other_formats_do_not_match(self, value: str) -> None:
        assert not functional_id.is_uuid(value)

    def test_setting_is_on_by_default(self) -> None:
        assert Settings.model_fields["FUNCTIONAL_ID_UUID_REQUIRED"].default is True


@pytest.mark.database
class TestUuidRequired:
    @pytest.fixture(autouse=True)
    def _overrides(self, async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
        async def override_get_db():
            yield async_session

        async def clean_scan(filedata: bytes) -> ScanResult:
            return ScanResult(passed_malware_scan=True, message="mocked clean file")

        monkeypatch.setattr(ca_areas, "scan_file_for_malware", clean_scan)
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", True)
        for app in APPS:
            app.dependency_overrides[verify_bearer_token] = TOKENS[app]
            app.dependency_overrides[get_async_db] = override_get_db
            app.dependency_overrides[get_async_db_read_only] = override_get_db
        yield
        for app in APPS:
            app.dependency_overrides.clear()

    @pytest.fixture
    async def area_id(self, async_session: AsyncSession) -> str:
        ca = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="ca-1"
        )
        area = await AreaFactory.create_async(
            async_session, area_id="area-1", competent_authority_id=ca.id
        )
        return area.area_id

    # ── POST areas ──────────────────────────────────────────────────────

    @pytest.mark.parametrize("supplied", ["my-area", UPPER], ids=["own-id", "upper"])
    async def test_area_new_id_that_is_no_lowercase_uuid_is_refused(
        self, async_session: AsyncSession, supplied: str
    ) -> None:
        response = await _post_area(supplied)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = response.json()["detail"][0]
        assert detail["type"] == "business_logic_error"
        assert "must be a lowercase UUID" in detail["msg"]
        # Refused before the claim: the ID stays free
        assert not await async_session.get(AreaIdentity, supplied)

    async def test_area_lowercase_uuid_is_accepted(self) -> None:
        response = await _post_area(LOWER)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["areaId"] == LOWER

    async def test_area_without_id_gets_a_generated_uuid(self) -> None:
        response = await _post_area(None)

        assert response.status_code == status.HTTP_201_CREATED
        assert functional_id.is_uuid(response.json()["areaId"])

    async def test_area_existing_own_id_can_still_be_versioned(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", False)
        assert (await _post_area("my-area")).status_code == status.HTTP_201_CREATED
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", True)
        # A version needs its own timestamp (SQLite has second precision)
        await asyncio.sleep(1.0)

        response = await _post_area("my-area", tag="v2")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["areaId"] == "my-area"

    async def test_area_own_id_of_another_ca_stays_a_duplicate(
        self, async_session: AsyncSession
    ) -> None:
        await AreaFactory.create_async(
            async_session, area_id="taken-area", competent_authority_id="other-ca"
        )

        response = await _post_area("taken-area")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"][0]["type"] == "duplicate_error"

    async def test_area_any_id_is_accepted_when_the_setting_is_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", False)

        assert (await _post_area("my-area")).status_code == status.HTTP_201_CREATED

    # ── POST activities and POST listings (bulk) ────────────────────────

    @pytest.mark.parametrize("kind", list(BULK))
    @pytest.mark.parametrize("supplied", ["my-id", UPPER], ids=["own-id", "upper"])
    async def test_bulk_new_id_that_is_no_lowercase_uuid_is_nok(
        self, area_id: str, kind: str, supplied: str
    ) -> None:
        id_field, result_key = BULK[kind][3], BULK[kind][4]

        response = await _post_bulk(kind, area_id, **{id_field: supplied})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        result = response.json()["results"][0]
        assert result["status"] == "NOK"
        assert result[id_field] == supplied
        assert result.get(result_key) is None
        detail = result["errors"]["detail"][0]
        assert detail["type"] == "business_logic_error"
        assert detail["loc"] == [id_field]
        assert "must be a lowercase UUID" in detail["msg"]

    @pytest.mark.parametrize("kind", list(BULK))
    async def test_bulk_lowercase_uuid_is_ok(self, area_id: str, kind: str) -> None:
        id_field, result_key = BULK[kind][3], BULK[kind][4]

        response = await _post_bulk(kind, area_id, **{id_field: LOWER})

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()["results"][0]
        assert result["status"] == "OK"
        assert result[result_key][id_field] == LOWER

    @pytest.mark.parametrize("kind", list(BULK))
    async def test_bulk_without_id_gets_a_generated_uuid(
        self, area_id: str, kind: str
    ) -> None:
        id_field, result_key = BULK[kind][3], BULK[kind][4]

        response = await _post_bulk(kind, area_id)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()["results"][0]
        assert functional_id.is_uuid(result[result_key][id_field])

    @pytest.mark.parametrize("kind", list(BULK))
    async def test_bulk_existing_own_id_can_still_be_versioned(
        self, area_id: str, kind: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        id_field, result_key = BULK[kind][3], BULK[kind][4]
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", False)
        first = await _post_bulk(kind, area_id, **{id_field: "my-id"})
        assert first.status_code == status.HTTP_201_CREATED
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", True)

        response = await _post_bulk(
            kind, area_id, **{id_field: "my-id", "url": "http://example.com/changed"}
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()["results"][0]
        assert result["status"] == "OK"
        assert result[result_key][id_field] == "my-id"
        assert result[result_key]["url"] == "http://example.com/changed"

    @pytest.mark.parametrize("kind", list(BULK))
    async def test_bulk_refused_item_leaves_the_others_ok(
        self, area_id: str, kind: str
    ) -> None:
        app, path, list_key, id_field, _result_key, build = BULK[kind]
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                path,
                json={
                    list_key: [
                        build(area_id, **{id_field: "my-id"}),
                        build(area_id, **{id_field: LOWER}),
                    ]
                },
                headers={"Authorization": "Bearer t"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert [r["status"] for r in response.json()["results"]] == ["NOK", "OK"]

    @pytest.mark.parametrize("kind", list(BULK))
    async def test_bulk_any_id_is_accepted_when_the_setting_is_off(
        self, area_id: str, kind: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FUNCTIONAL_ID_UUID_REQUIRED", False)

        response = await _post_bulk(kind, area_id, **{BULK[kind][3]: "my-id"})

        assert response.status_code == status.HTTP_201_CREATED
