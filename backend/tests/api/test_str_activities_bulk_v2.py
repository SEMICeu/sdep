"""Tests for POST /str/{v1,v2}/activities/bulk: the rules that v1 backported from v2.

UTC-only timestamps, the activity regulation check and the widened `url`,
`fullAddress` and `registrationNumber` apply to both versions. The widened
fields are proven round trip through the CA v1, CA v2 and STA v1 reads.
"""

from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.sta.v1 import app_sta_v1
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


def _sta_token() -> dict[str, Any]:
    return {
        "sub": "sta",
        "client_id": "cbs01",
        "client_name": "Statistics Authority",
        "realm_access": {"roles": ["sdep_sta", "sdep_read"]},
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


@pytest.fixture(params=[app_str_v1, app_str_v2], ids=["v1", "v2"])
def str_app(request):
    return request.param


@pytest.mark.database
class TestStrBulk:
    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        async def override_get_db():
            yield async_session

        for app, token in (
            (app_str_v1, _str_token),
            (app_str_v2, _str_token),
            (app_ca_v1, _ca_token),
            (app_ca_v2, _ca_token),
            (app_sta_v1, _sta_token),
        ):
            app.dependency_overrides[verify_bearer_token] = token
            app.dependency_overrides[get_async_db] = override_get_db
            app.dependency_overrides[get_async_db_read_only] = override_get_db
        yield
        for app in (app_str_v1, app_str_v2, app_ca_v1, app_ca_v2, app_sta_v1):
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

    async def test_rejects_listing_only_area_per_item(
        self, setup_overrides, areas, str_app
    ):
        response = await _post(
            str_app,
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

    async def test_unknown_area_is_still_not_found(
        self, setup_overrides, areas, str_app
    ):
        """The regulation check must not turn an unknown area into a regulation error."""
        response = await _post(str_app, [_activity("no-such-area", "n")])

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        error = response.json()["results"][0]["errors"]["detail"][0]
        assert error["type"] == "not_found_error"

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
    async def test_rejects_non_utc_timestamps(
        self, setup_overrides, areas, str_app, start, end
    ):
        response = await _post(
            str_app,
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

    async def test_accepts_utc_with_z_and_plus_zero(
        self, setup_overrides, areas, str_app
    ):
        response = await _post(str_app, [_activity(areas["all"], "u")])

        assert response.status_code == status.HTTP_201_CREATED

    # ── Widened maxima, round trip through every reader ──────

    async def test_widened_fields_round_trip(self, setup_overrides, areas, str_app):
        url = "http://example.com/" + "u" * (2048 - len("http://example.com/"))
        full_address = "F" * 328
        registration_number = "R" * 128
        posted = await _post(
            str_app,
            [
                _activity(
                    areas["all"],
                    "w",
                    url=url,
                    registrationNumber=registration_number,
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

        for app in (app_ca_v1, app_ca_v2, app_sta_v1):
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
            assert activity["registrationNumber"] == registration_number

    async def test_maximum_is_accepted_and_one_over_is_rejected(
        self, setup_overrides, areas, str_app
    ):
        def url(length: int) -> str:
            return "http://x/" + "u" * (length - len("http://x/"))

        def address(length: int) -> dict[str, Any]:
            return {
                "thoroughfare": "T",
                "postCode": "1234AB",
                "postName": "P",
                "fullAddress": "F" * length,
            }

        at_max = await _post(
            str_app,
            [
                _activity(
                    areas["all"],
                    "m1",
                    url=url(2048),
                    address=address(328),
                    registrationNumber="R" * 128,
                )
            ],
        )
        assert at_max.status_code == status.HTTP_201_CREATED, at_max.text

        response = await _post(
            str_app,
            [
                _activity(areas["all"], "o1", url=url(2049)),
                _activity(areas["all"], "o2", address=address(329)),
                _activity(areas["all"], "o3", registrationNumber="R" * 129),
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
        assert ("registrationNumber",) in locs


class TestStrContract:
    """Contract-level checks that need no database."""

    @pytest.mark.parametrize(
        ("app", "operation_id"),
        [(app_str_v1, "postActivitiesBulk"), (app_str_v2, "postActivitiesBulkV2")],
        ids=["v1", "v2"],
    )
    def test_openapi_documents_the_rules(self, app, operation_id: str):
        schema = app.openapi()
        post = schema["paths"]["/activities/bulk"]["post"]
        assert post["operationId"] == operation_id
        assert "regulation_error" in post["description"]
        schemas = schema["components"]["schemas"]
        temporal = schemas["CommonTemporalRequest"]["properties"]
        assert "UTC" in temporal["startDatetime"]["description"]
        request = schemas["ActivityRequest"]["properties"]
        assert request["url"]["maxLength"] == 2048
        assert request["registrationNumber"]["maxLength"] == 128
        address = schemas["CommonAddressRequest"]["properties"]
        assert address["fullAddress"]["maxLength"] == 328

    def test_every_activity_response_declares_the_maxima(self):
        for app in (app_ca_v1, app_ca_v2, app_str_v1, app_str_v2, app_sta_v1):
            schemas = app.openapi()["components"]["schemas"]
            response = schemas["ActivityResponse"]["properties"]
            assert response["url"]["maxLength"] == 2048
            assert response["registrationNumber"]["maxLength"] == 128
            assert (
                schemas["CommonAddressResponse"]["properties"]["fullAddress"][
                    "maxLength"
                ]
                == 328
            )
