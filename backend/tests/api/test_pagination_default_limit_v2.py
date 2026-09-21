"""STR v2 and CA v2 list endpoints return at most 1000 records per call.

Proven with 1001 rows: the v2 apps return 1000 without a `limit`, the v1 apps
return everything. The contract (declared default) is checked alongside.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.str.v1 import app_str_v1
from app.api.domains.str.v2 import app_str_v2
from app.db.config import get_async_db, get_async_db_read_only
from app.enums import ActivityStatus, Regulation
from app.models.activity import Activity
from app.models.area import Area
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import CompetentAuthorityFactory, PlatformFactory

CA_ID = "0363"
ROWS = 1001


def _str_token() -> dict[str, Any]:
    return {"sub": "str", "realm_access": {"roles": ["sdep_str", "sdep_read"]}}


def _ca_token() -> dict[str, Any]:
    return {
        "sub": "ca",
        "client_id": CA_ID,
        "client_name": "Gemeente Amsterdam",
        "realm_access": {"roles": ["sdep_ca", "sdep_read"]},
    }


async def _get(app, path: str) -> list[dict[str, Any]]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(path, headers={"Authorization": "Bearer t"})
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    return body["areas"] if "areas" in body else body["activities"]


@pytest.mark.database
class TestDefaultLimit:
    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        async def override_get_db():
            yield async_session

        for app, token in (
            (app_str_v1, _str_token),
            (app_str_v2, _str_token),
            (app_ca_v1, _ca_token),
            (app_ca_v2, _ca_token),
        ):
            app.dependency_overrides[verify_bearer_token] = token
            app.dependency_overrides[get_async_db] = override_get_db
            app.dependency_overrides[get_async_db_read_only] = override_get_db
        yield
        for app in (app_str_v1, app_str_v2, app_ca_v1, app_ca_v2):
            app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def many_areas(self, async_session: AsyncSession) -> int:
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id=CA_ID,
            competent_authority_name="Gemeente Amsterdam",
        )
        async_session.add_all(
            Area(
                area_id=f"area-{i:04d}",
                area_name=f"Area {i}",
                regulation=Regulation.all,
                competent_authority_id=ca.id,
                filename="a.zip",
                filedata=b"zip",
            )
            for i in range(ROWS)
        )
        await async_session.flush()
        return ca.id

    @pytest_asyncio.fixture
    async def many_activities(
        self, async_session: AsyncSession, many_areas: int
    ) -> None:
        platform = await PlatformFactory.create_async(async_session)
        area_id = await _area_pk(async_session, many_areas)
        start = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
        async_session.add_all(
            Activity(
                activity_id=f"activity-{i:04d}",
                status=ActivityStatus.finished,
                platform_id=platform.id,
                area_id=area_id,
                url=f"http://example.com/{i}",
                address_thoroughfare="T",
                address_post_code="1234AB",
                address_post_name="P",
                address_full_address="T 1, 1234AB P",
                registration_number="REG",
                number_of_guests=1,
                country_of_guests=["NLD"],
                temporal_start_date_time=start + timedelta(hours=i),
                temporal_end_date_time=start + timedelta(hours=i, days=1),
            )
            for i in range(ROWS)
        )
        await async_session.flush()

    @pytest.mark.parametrize(
        "app,expected",
        [(app_str_v1, ROWS), (app_str_v2, 1000)],
        ids=["str-v1-unlimited", "str-v2-capped"],
    )
    async def test_str_areas_default_limit(
        self, setup_overrides, many_areas, app, expected
    ):
        assert len(await _get(app, "/areas")) == expected

    @pytest.mark.parametrize(
        "app,expected",
        [(app_ca_v1, ROWS), (app_ca_v2, 1000)],
        ids=["ca-v1-unlimited", "ca-v2-capped"],
    )
    async def test_ca_areas_default_limit(
        self, setup_overrides, many_areas, app, expected
    ):
        assert len(await _get(app, "/areas")) == expected

    @pytest.mark.parametrize(
        "app,expected",
        [(app_ca_v1, ROWS), (app_ca_v2, 1000)],
        ids=["ca-v1-unlimited", "ca-v2-capped"],
    )
    async def test_ca_activities_default_limit(
        self, setup_overrides, many_activities, app, expected
    ):
        assert len(await _get(app, "/activities")) == expected

    async def test_v2_second_page_completes_the_set(self, setup_overrides, many_areas):
        second = await _get(app_str_v2, "/areas?offset=1000")
        assert len(second) == 1


async def _area_pk(session: AsyncSession, ca_pk: int) -> int:
    from sqlalchemy import select

    return (
        await session.execute(
            select(Area.id).where(Area.competent_authority_id == ca_pk).limit(1)
        )
    ).scalar_one()


class TestDefaultLimitContract:
    @pytest.mark.parametrize(
        "app,path,default",
        [
            (app_str_v1, "/areas", None),
            (app_str_v2, "/areas", 1000),
            (app_ca_v1, "/areas", None),
            (app_ca_v2, "/areas", 1000),
            (app_ca_v1, "/activities", None),
            (app_ca_v2, "/activities", 1000),
        ],
        ids=[
            "str-v1",
            "str-v2",
            "ca-v1-areas",
            "ca-v2-areas",
            "ca-v1-activities",
            "ca-v2-activities",
        ],
    )
    def test_limit_default_is_declared(self, app, path, default):
        parameters = app.openapi()["paths"][path]["get"]["parameters"]
        limit = next(p for p in parameters if p["name"] == "limit")
        assert limit["schema"].get("default") == default
        assert (
            limit["schema"].get(
                "maximum", limit["schema"].get("anyOf", [{}])[0].get("maximum")
            )
            == 1000
        )
