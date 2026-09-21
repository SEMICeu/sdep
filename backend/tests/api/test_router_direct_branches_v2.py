"""Direct calls into the v2 router functions.

HTTP-driven tests do not yield line coverage for the awaited endpoint bodies in
this suite (see test_router_direct_branches.py), so each v2 function is called
directly with mocked services. Behaviour is proven in test_str_activities_bulk_v2.py
and test_pagination_default_limit_v2.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest
from app.api.common.auth_dependencies import Client, NamedClient
from app.api.common.pagination import PaginationParams
from app.api.domains.ca.routers import areas_list_v2 as ca_areas_list_v2
from app.api.domains.str.routers import activities_bulk_v2 as str_activities_bulk_v2
from app.api.domains.str.routers import areas_list_v2 as str_areas_list_v2
from app.schemas.activity import ActivityRequestV2
from app.schemas.activity_bulk import ActivityBulkRequestV2, ActivityBulkResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _area_row():
    return SimpleNamespace(
        area_id="area-1",
        area_name="Area",
        regulation="all",
        filename="area.zip",
        competent_authority=SimpleNamespace(
            competent_authority_id="ca-1",
            competent_authority_name="CA",
        ),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_str_activities_bulk_v2_passes_the_v2_item_model_and_regulation_flag(
    monkeypatch,
):
    service = AsyncMock(
        return_value=ActivityBulkResponse(
            totalReceived=1, succeeded=1, failed=0, results=[]
        )
    )
    monkeypatch.setattr(
        str_activities_bulk_v2.activity_bulk_service, "create_activities_bulk", service
    )
    request = ActivityBulkRequestV2.model_construct(activities=[{"any": "value"}])

    response = await str_activities_bulk_v2.post_activities_bulk(
        request,
        client=NamedClient(id="str-1", name="STR"),
        session=cast("AsyncSession", object()),
    )

    assert response.status_code == 201
    service.assert_awaited_once()
    assert service.await_args is not None
    kwargs = service.await_args.kwargs
    assert kwargs["item_model"] is ActivityRequestV2
    assert kwargs["require_activity_regulation"] is True


@pytest.mark.asyncio
async def test_str_areas_list_v2_direct(monkeypatch):
    monkeypatch.setattr(
        str_areas_list_v2.area, "get_areas", AsyncMock(return_value=[_area_row()])
    )

    areas = await str_areas_list_v2.get_areas(
        pagination=PaginationParams(offset=0, limit=1000),
        session=cast("AsyncSession", object()),
    )

    assert areas.areas[0].area_id == "area-1"


@pytest.mark.asyncio
async def test_ca_areas_list_v2_direct(monkeypatch):
    monkeypatch.setattr(
        ca_areas_list_v2.area_service,
        "get_areas_by_client_id",
        AsyncMock(return_value=[_area_row()]),
    )

    response = await ca_areas_list_v2.get_own_areas(
        client=Client(id="ca-1", name="CA"),
        pagination=PaginationParams(offset=0, limit=1000),
        session=cast("AsyncSession", object()),
    )

    assert json.loads(bytes(response.body))["areas"][0]["areaId"] == "area-1"
