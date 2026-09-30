"""Tests for the AMA (activity monitoring authority) activities API: a STA v1 read with its own role."""

from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.ama.v1 import app_ama_v1
from app.db.config import get_async_db_read_only
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import (
    ActivityFactory,
    AreaFactory,
    CompetentAuthorityFactory,
    PlatformFactory,
)


def _token(roles: list[str]):
    def mock() -> dict[str, Any]:
        return {
            "sub": "ama",
            "client_id": "ama01",
            "client_name": "Activity Monitor",
            "realm_access": {"roles": roles},
        }

    return mock


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app_ama_v1), base_url="http://test"
    ) as client:
        return await client.get(path, headers={"Authorization": "Bearer t"})


@pytest.mark.database
class TestAMAActivitiesAPI:
    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        app_ama_v1.dependency_overrides[verify_bearer_token] = _token(
            ["sdep_ama", "sdep_read"]
        )

        async def override_get_db_read_only():
            yield async_session

        app_ama_v1.dependency_overrides[get_async_db_read_only] = (
            override_get_db_read_only
        )
        yield
        app_ama_v1.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def test_data(self, async_session: AsyncSession) -> dict[str, Any]:
        ca_a = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="ca-a"
        )
        ca_b = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="ca-b"
        )
        area_a = await AreaFactory.create_async(
            async_session, area_id="area-a", competent_authority_id=ca_a.id
        )
        area_b = await AreaFactory.create_async(
            async_session, area_id="area-b", competent_authority_id=ca_b.id
        )
        platform = await PlatformFactory.create_async(
            async_session, platform_id="str01"
        )
        for _ in range(3):
            await ActivityFactory.create_async(
                async_session, area_id=area_a.id, platform_id=platform.id
            )
        await ActivityFactory.create_async(
            async_session, area_id=area_b.id, platform_id=platform.id
        )
        return {"area_a": area_a.area_id, "ca_b": ca_b.competent_authority_id}

    async def test_reads_all_activities_across_competent_authorities(
        self, setup_overrides, test_data
    ):
        response = await _get("/activities")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["activities"]) == 4
        assert (await _get("/activities/count")).json() == {"count": 4}

    async def test_filters_and_pagination(self, setup_overrides, test_data):
        response = await _get(f"/activities?areaId={test_data['area_a']}")
        assert len(response.json()["activities"]) == 3
        response = await _get(
            f"/activities/count?competentAuthorityId={test_data['ca_b']}"
        )
        assert response.json() == {"count": 1}
        response = await _get("/activities?offset=3&limit=1")
        assert len(response.json()["activities"]) == 1
        response = await _get("/activities?createdAtFrom=2026-01-01T00:00:00+02:00")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_requires_ama_role(self, setup_overrides):
        app_ama_v1.dependency_overrides[verify_bearer_token] = _token(
            ["sdep_sta", "sdep_read"]
        )
        response = await _get("/activities")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "sdep_ama" in response.json()["detail"][0]["msg"]

    async def test_write_methods_not_allowed(self, setup_overrides):
        async with AsyncClient(
            transport=ASGITransport(app=app_ama_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/activities", json={}, headers={"Authorization": "Bearer t"}
            )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
