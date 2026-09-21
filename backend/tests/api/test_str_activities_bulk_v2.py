"""Tests for POST /str/v2/activities/bulk: what v2 tightens versus v1.

UTC-only timestamps and the activity regulation check apply to v2 only; the
v1 cases here prove v1 is unchanged. The widened
`fullAddress` and `url`) apply to v1 as well and are proven round trip through
the CA v1, CA v2 and REP v1 reads.
"""

from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.rep.v1 import app_rep_v1
from app.api.domains.str.v1 import app_str_v1
from app.api.domains.str.v2 import app_str_v2
from app.db.config import get_async_db, get_async_db_read_only
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory, CompetentAuthorityFactory

CA_ID = "0363"
UTC_START = "2025-06-01T14:00:00Z"
UTC_END = "2025-06-07T11:00:00+00:00"


def _str_token() -> dict[str, Any]:
    return {
        "sub": "str",
        "client_id": "str-v2-test",
        "client_name": "Test STR v2",
        "realm_access": {"roles": ["sdep_str", "sdep_write", "sdep_read"]},
    }


def _ca_token() -> dict[str, Any]:
    return {
        "sub": "ca",
        "client_id": CA_ID,
        "client_name": "Gemeente Amsterdam",
        "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
    }


def _rep_token() -> dict[str, Any]:
    return {
        "sub": "rep",
        "client_id": "cbs01",
        "client_name": "Statistics Office",
        "realm_access": {"roles": ["sdep_rep", "sdep_read"]},
    }


def _activity(area_id: str, suffix: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "areaId": area_id,
        "url": f"http://example.com/v2-{suffix}",
        "registrationNumber": f"REG-{suffix}",
        "address": {
            "thoroughfare": "Turfmarkt",
            "locatorDesignatorNumber": 147,
            "postCode": "2500EA",
            "postName": "Den Haag",
            "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
        },
        "temporal": {"startDatetime": UTC_START, "endDatetime": UTC_END},
        "numberOfGuests": 1,
        "countryOfGuests": ["NLD"],
    }
    base.update(overrides)
    return base


async def _post(app, activities: list[dict[str, Any]]):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/activities/bulk",
            json={"activities": activities},
            headers={"Authorization": "Bearer t"},
        )


@pytest.mark.database
class TestStrBulkV2:
    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        async def override_get_db():
            yield async_session

        for app, token in (
            (app_str_v1, _str_token),
            (app_str_v2, _str_token),
            (app_ca_v1, _ca_token),
            (app_ca_v2, _ca_token),
            (app_rep_v1, _rep_token),
        ):
            app.dependency_overrides[verify_bearer_token] = token
            app.dependency_overrides[get_async_db] = override_get_db
            app.dependency_overrides[get_async_db_read_only] = override_get_db
        yield
        for app in (app_str_v1, app_str_v2, app_ca_v1, app_ca_v2, app_rep_v1):
            app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def areas(self, async_session: AsyncSession) -> dict[str, str]:
        """One area per regulation type, all owned by CA 0363."""
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id=CA_ID,
            competent_authority_name="Gemeente Amsterdam",
        )
        ids: dict[str, str] = {}
        for regulation in ("listing", "activity", "all"):
            area = await AreaFactory.create_async(
                async_session,
                area_id=f"area-{regulation}",
                area_name=f"Area {regulation}",
                regulation=regulation,
                competent_authority_id=ca.id,
                filename=f"{regulation}.zip",
                filedata=b"zip",
            )
            ids[regulation] = area.area_id
        return ids

    # ── Regulation check ─────────────────────────────────────

    async def test_v2_rejects_listing_only_area_per_item(self, setup_overrides, areas):
        response = await _post(
            app_str_v2,
            [
                _activity(areas["listing"], "l"),
                _activity(areas["activity"], "a"),
                _activity(areas["all"], "x"),
            ],
        )

        assert response.status_code == status.HTTP_200_OK  # partial success
        data = response.json()
        assert (data["succeeded"], data["failed"]) == (2, 1)
        nok = data["results"][0]
        assert nok["status"] == "NOK"
        assert nok["errors"]["detail"] == [
            {
                "msg": f"Area with areaId '{areas['listing']}' is regulated for listing only",
                "type": "regulation_error",
                "loc": ["areaId"],
            }
        ]
        assert [r["status"] for r in data["results"][1:]] == ["OK", "OK"]

    async def test_v2_unknown_area_is_still_not_found(self, setup_overrides, areas):
        """The regulation check must not turn an unknown area into a regulation error."""
        response = await _post(app_str_v2, [_activity("no-such-area", "n")])

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        error = response.json()["results"][0]["errors"]["detail"][0]
        assert error["type"] == "not_found_error"

    async def test_v1_still_accepts_listing_only_area(self, setup_overrides, areas):
        response = await _post(app_str_v1, [_activity(areas["listing"], "l1")])

        assert response.status_code == status.HTTP_201_CREATED

    # ── UTC-only timestamps ──────────────────────────────────

    @pytest.mark.parametrize(
        "start,end",
        [
            ("2025-06-01T14:00:00", "2025-06-07T11:00:00Z"),  # naive start
            ("2025-06-01T14:00:00Z", "2025-06-07T11:00:00+02:00"),  # offset end
            ("2025-06-01", "2025-06-07T11:00:00Z"),  # date-only start
        ],
        ids=["naive", "offset", "date-only"],
    )
    async def test_v2_rejects_non_utc_timestamps(
        self, setup_overrides, areas, start, end
    ):
        response = await _post(
            app_str_v2,
            [
                _activity(
                    areas["all"],
                    "t",
                    temporal={"startDatetime": start, "endDatetime": end},
                )
            ],
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = response.json()["results"][0]["errors"]["detail"]
        assert any(
            "UTC with offset Z or +00:00" in error["msg"]
            and error["loc"][0] == "temporal"
            for error in detail
        )

    async def test_v2_accepts_utc_with_z_and_plus_zero(self, setup_overrides, areas):
        response = await _post(app_str_v2, [_activity(areas["all"], "u")])

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize(
        "start,end",
        [
            ("2025-06-01T14:00:00", "2025-06-07T11:00:00+02:00"),
            ("2025-06-01", "2025-06-07T11:00:00Z"),
        ],
        ids=["naive-with-offset-end", "date-only"],
    )
    async def test_v1_still_accepts_naive_and_date_only(
        self, setup_overrides, areas, start, end
    ):
        """Also covers the naive/aware comparison that used to raise TypeError in v1."""
        response = await _post(
            app_str_v1,
            [
                _activity(
                    areas["all"],
                    "n",
                    temporal={"startDatetime": start, "endDatetime": end},
                )
            ],
        )

        assert response.status_code == status.HTTP_201_CREATED

    # ── Widened maxima, round trip through every reader ──

    async def test_widened_url_and_full_address_round_trip(
        self, setup_overrides, areas
    ):
        url = "http://example.com/" + "u" * (2048 - len("http://example.com/"))
        full_address = "F" * 328
        posted = await _post(
            app_str_v1,
            [
                _activity(
                    areas["all"],
                    "w",
                    url=url,
                    address={
                        "thoroughfare": "T",
                        "postCode": "1234AB",
                        "postName": "P",
                        "fullAddress": full_address,
                    },
                )
            ],
        )
        assert posted.status_code == status.HTTP_201_CREATED, posted.text

        for app in (app_ca_v1, app_ca_v2, app_rep_v1):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/activities", headers={"Authorization": "Bearer t"}
                )
            assert response.status_code == status.HTTP_200_OK
            activity = response.json()["activities"][0]
            assert activity["url"] == url
            assert activity["address"]["fullAddress"] == full_address

    async def test_one_over_the_maximum_is_rejected(self, setup_overrides, areas):
        response = await _post(
            app_str_v1,
            [
                _activity(areas["all"], "o1", url="http://x/" + "u" * 2040),  # 2049
                _activity(
                    areas["all"],
                    "o2",
                    address={
                        "thoroughfare": "T",
                        "postCode": "1234AB",
                        "postName": "P",
                        "fullAddress": "F" * 329,
                    },
                ),
            ],
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        locs = [
            tuple(error["loc"])
            for item in response.json()["results"]
            for error in item["errors"]["detail"]
        ]
        assert ("url",) in locs
        assert ("address", "fullAddress") in locs


class TestStrV2Contract:
    """Contract-level checks that need no database."""

    def test_v2_openapi_documents_the_tightening(self):
        schema = app_str_v2.openapi()
        temporal = schema["components"]["schemas"]["CommonTemporalRequestV2"][
            "properties"
        ]
        assert "UTC" in temporal["startDatetime"]["description"]
        assert (
            schema["paths"]["/activities/bulk"]["post"]["operationId"]
            == "postActivitiesBulkV2"
        )
        assert (
            "regulation_error"
            in schema["paths"]["/activities/bulk"]["post"]["description"]
        )

    def test_v1_openapi_keeps_its_operation_ids_and_widened_maxima(self):
        schema = app_str_v1.openapi()
        assert (
            schema["paths"]["/activities/bulk"]["post"]["operationId"]
            == "postActivitiesBulk"
        )
        request = schema["components"]["schemas"]["ActivityRequest"]["properties"]
        assert request["url"]["maxLength"] == 2048
        address = schema["components"]["schemas"]["CommonAddressRequest"]["properties"]
        assert address["fullAddress"]["maxLength"] == 328

    def test_ca_v1_response_declares_no_maxima_but_ca_v2_and_rep_v1_do(self):
        v1 = app_ca_v1.openapi()["components"]["schemas"]
        assert "maxLength" not in v1["ActivityResponse"]["properties"]["url"]
        assert (
            "maxLength" not in v1["CommonAddressResponse"]["properties"]["fullAddress"]
        )
        for app in (app_ca_v2, app_rep_v1):
            schemas = app.openapi()["components"]["schemas"]
            assert schemas["ActivityResponse"]["properties"]["url"]["maxLength"] == 2048
            assert (
                schemas["CommonAddressResponse"]["properties"]["fullAddress"][
                    "maxLength"
                ]
                == 328
            )
