"""Tests for the reference data reads: platforms, competent authorities, areas.

Every audience that filters on these IDs can look them up in the same API
(see app/api/common/reference_routers.py). CA v2 gets platforms only.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.ama.v1 import app_ama_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.lma.v2 import app_lma_v2
from app.api.domains.lsa.v2 import app_lsa_v2
from app.api.domains.sta.v1 import app_sta_v1
from app.api.domains.sta.v2 import app_sta_v2
from app.db.config import get_async_db_read_only
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import (
    AreaFactory,
    CompetentAuthorityFactory,
    PlatformFactory,
)

APPS = {
    app_ama_v1: "sdep_ama",
    app_sta_v1: "sdep_sta",
    app_sta_v2: "sdep_sta",
    app_lma_v2: "sdep_lma",
    app_lsa_v2: "sdep_lsa",
    app_ca_v2: "sdep_ca",
}
FULL_APPS = [app for app in APPS if app is not app_ca_v2]
ENDED = datetime(2025, 6, 1, tzinfo=UTC)
PLATFORM_PATHS = ["/platforms", "/platforms/count"]
OTHER_PATHS = [
    "/competent-authorities",
    "/competent-authorities/count",
    "/areas",
    "/areas/count",
]


def _token(roles: list[str]):
    def mock() -> dict[str, Any]:
        return {
            "sub": "reader",
            "client_id": "reader",
            "realm_access": {"roles": roles},
        }

    return mock


async def _get(app, path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers={"Authorization": "Bearer t"})


@pytest.mark.database
class TestReferenceData:
    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        async def override_get_db():
            yield async_session

        for app, role in APPS.items():
            app.dependency_overrides[verify_bearer_token] = _token([role, "sdep_read"])
            app.dependency_overrides[get_async_db_read_only] = override_get_db
        yield
        for app in APPS:
            app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def data(self, async_session: AsyncSession) -> None:
        """One current and one ended version of each resource."""
        await PlatformFactory.create_async(
            async_session, platform_id="platform-a", platform_name="Platform A"
        )
        await PlatformFactory.create_async(
            async_session, platform_id="platform-old", client_id="old", ended_at=ENDED
        )
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="ca-a",
            competent_authority_name="Authority A",
        )
        await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="ca-old",
            client_id="ca-old",
            ended_at=ENDED,
        )
        await AreaFactory.create_async(
            async_session,
            area_id="area-a",
            competent_authority_id=ca.id,
            filename="a.zip",
            filedata=b"zip-a",
        )
        await AreaFactory.create_async(
            async_session,
            area_id="area-old",
            competent_authority_id=ca.id,
            filename="old.zip",
            filedata=b"zip-old",
            ended_at=ENDED,
        )

    @pytest.mark.parametrize("app", list(APPS))
    async def test_platforms(self, setup_overrides, data, app):
        response = await _get(app, "/platforms")
        assert response.status_code == status.HTTP_200_OK, response.text
        platforms = response.json()["platforms"]
        assert [p["platformId"] for p in platforms] == ["platform-a"]
        assert set(platforms[0]) == {"platformId", "platformName", "createdAt"}
        assert platforms[0]["platformName"] == "Platform A"
        assert (await _get(app, "/platforms/count")).json() == {"count": 1}

    @pytest.mark.parametrize("app", FULL_APPS)
    async def test_competent_authorities(self, setup_overrides, data, app):
        response = await _get(app, "/competent-authorities")
        assert response.status_code == status.HTTP_200_OK, response.text
        authorities = response.json()["competentAuthorities"]
        assert [ca["competentAuthorityId"] for ca in authorities] == ["ca-a"]
        assert set(authorities[0]) == {
            "competentAuthorityId",
            "competentAuthorityName",
            "createdAt",
        }
        assert authorities[0]["competentAuthorityName"] == "Authority A"
        assert (await _get(app, "/competent-authorities/count")).json() == {"count": 1}

    @pytest.mark.parametrize("app", FULL_APPS)
    async def test_areas(self, setup_overrides, data, app):
        response = await _get(app, "/areas")
        assert response.status_code == status.HTTP_200_OK, response.text
        areas = response.json()["areas"]
        assert [a["areaId"] for a in areas] == ["area-a"]
        assert areas[0]["competentAuthorityId"] == "ca-a"
        assert (await _get(app, "/areas/count")).json() == {"count": 1}

    @pytest.mark.parametrize("app", list(APPS))
    async def test_pagination(self, setup_overrides, async_session, app):
        for n in range(3):
            await PlatformFactory.create_async(async_session, platform_id=f"p{n}")
        response = await _get(app, "/platforms?offset=1&limit=1")
        assert len(response.json()["platforms"]) == 1
        response = await _get(app, "/platforms?limit=1001")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_ca_v2_has_platforms_only(self, setup_overrides, data):
        response = await _get(app_ca_v2, "/competent-authorities")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("app", FULL_APPS)
    async def test_no_read_by_id(self, setup_overrides, data, app):
        # No read by ID, see reference_routers.py; CA v2 keeps its own area download
        for path in (
            "/platforms/platform-a",
            "/competent-authorities/ca-a",
            "/areas/area-a",
        ):
            response = await _get(app, path)
            assert response.status_code == status.HTTP_404_NOT_FOUND, path

    @pytest.mark.parametrize(
        ("app", "path"),
        [(app, path) for app in APPS for path in PLATFORM_PATHS]
        + [(app, path) for app in FULL_APPS for path in OTHER_PATHS],
    )
    async def test_requires_audience_role(self, setup_overrides, data, app, path):
        app.dependency_overrides[verify_bearer_token] = _token(["sdep_read"])
        response = await _get(app, path)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_missing_name_is_omitted(self, setup_overrides, async_session):
        await PlatformFactory.create_async(
            async_session, platform_id="nameless", platform_name=None
        )
        await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id="nameless",
            competent_authority_name=None,
        )
        body = (await _get(app_lma_v2, "/platforms")).json()
        assert "platformName" not in body["platforms"][0]
        body = (await _get(app_lma_v2, "/competent-authorities")).json()
        assert "competentAuthorityName" not in body["competentAuthorities"][0]
