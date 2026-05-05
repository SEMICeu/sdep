from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest
from app.api.common.auth_dependencies import Client, NamedClient
from app.api.common.routers import (
    ca_activities,
    ca_areas,
    str_activities_bulk,
    str_areas,
)
from app.models.address import Address
from app.models.temporal import Temporal
from app.schemas.activity_bulk import (
    ActivityBulkRequest,
    ActivityBulkResponse,
    ActivityBulkResultItem,
)
from app.schemas.error import ErrorDetail, ErrorResponse
from fastapi import HTTPException, UploadFile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_ca_activities_direct_branches(monkeypatch):
    session = cast("AsyncSession", object())
    monkeypatch.setattr(
        ca_activities.activity,
        "get_activity_list",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    activity_id="activity-1",
                    activity_name="Activity",
                    status="finished",
                    area_id_functional="area-1",
                    competent_authority_id_functional="ca-1",
                    competent_authority_name="CA",
                    url="http://example.com",
                    address=Address(
                        "Street",
                        1,
                        None,
                        None,
                        "1234AB",
                        "City",
                        "Street 1, 1234AB City",
                    ),
                    registration_number="REG-1",
                    number_of_guests=2,
                    country_of_guests=["NLD", "DEU"],
                    temporal=Temporal(
                        datetime(2025, 1, 1, tzinfo=UTC),
                        datetime(2025, 1, 2, tzinfo=UTC),
                    ),
                    platform_id_functional="str-1",
                    platform_name="STR",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        ),
    )
    result = await ca_activities.get_activities(
        client=Client(id="ca-1", name="CA"),
        session=session,
        offset=0,
        limit=None,
    )
    assert result.activities[0].activity_id == "activity-1"

    monkeypatch.setattr(
        ca_activities.activity,
        "count_activity_by_competent_authority",
        AsyncMock(return_value=5),
    )
    count = await ca_activities.count_activities(
        client=Client(id="ca-1", name="CA"), session=session
    )
    assert count.count == 5


@pytest.mark.asyncio
async def test_ca_areas_direct_branches(monkeypatch):
    session = cast("AsyncSession", object())

    with pytest.raises(HTTPException, match="at most 64 characters"):
        await ca_areas.post_area(
            client=NamedClient(id="ca-1", name="CA"),
            session=session,
            areaId=None,
            areaName="x" * 65,
            regulation=None,
            file=UploadFile(filename="area.zip", file=io.BytesIO(b"data")),
        )

    monkeypatch.setattr(
        ca_areas.area_service,
        "create_area",
        AsyncMock(
            return_value=SimpleNamespace(
                area_id="area-1",
                area_name="Area",
                regulation="all",
                filename="area.zip",
                created_at="2025-01-01T00:00:00Z",
            )
        ),
    )
    created = await ca_areas.post_area(
        client=NamedClient(id="ca-1", name="CA"),
        session=session,
        areaId=None,
        areaName=None,
        regulation=None,
        file=UploadFile(filename="area.zip", file=io.BytesIO(b"data")),
    )
    assert json.loads(bytes(created.body))["areaId"] == "area-1"

    monkeypatch.setattr(
        ca_areas.area_service,
        "get_areas_by_competent_authority",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    area_id="area-1",
                    area_name="Area",
                    regulation="all",
                    filename="area.zip",
                    competent_authority_id_functional="ca-1",
                    competent_authority_name="CA",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        ),
    )
    own_areas = await ca_areas.get_own_areas(
        client=Client(id="ca-1", name="CA"), session=session, offset=0, limit=None
    )
    assert json.loads(bytes(own_areas.body))["areas"][0]["areaId"] == "area-1"

    monkeypatch.setattr(
        ca_areas.area_service,
        "count_areas_by_competent_authority",
        AsyncMock(return_value=2),
    )
    count = await ca_areas.count_own_areas(
        client=Client(id="ca-1", name="CA"), session=session
    )
    assert count.count == 2

    monkeypatch.setattr(
        ca_areas.area_service, "get_own_area_by_id", AsyncMock(return_value=None)
    )
    with pytest.raises(HTTPException, match="not found"):
        await ca_areas.get_own_area(
            client=Client(id="ca-1", name="CA"), areaId="area-1", session=session
        )
    monkeypatch.setattr(
        ca_areas.area_service,
        "get_own_area_by_id",
        AsyncMock(
            return_value=SimpleNamespace(filedata=b"zipdata", filename="owned.zip")
        ),
    )
    response = await ca_areas.get_own_area(
        client=Client(id="ca-1", name="CA"), areaId="area-1", session=session
    )
    assert response.headers["content-disposition"] == 'attachment; filename="owned.zip"'

    monkeypatch.setattr(ca_areas.area_service, "delete_area", AsyncMock())
    deleted = await ca_areas.delete_area(
        client=Client(id="ca-1", name="CA"), areaId="area-1", session=session
    )
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_str_activities_bulk_direct_branches(monkeypatch):
    request = ActivityBulkRequest.model_construct(activities=[{"any": "value"}])
    session = cast("AsyncSession", object())
    monkeypatch.setattr(
        str_activities_bulk.activity_bulk_service,
        "create_activities_bulk",
        AsyncMock(
            side_effect=[
                ActivityBulkResponse(
                    totalReceived=1, succeeded=1, failed=0, results=[]
                ),
                ActivityBulkResponse(
                    totalReceived=1, succeeded=1, failed=1, results=[]
                ),
                ActivityBulkResponse(
                    totalReceived=1,
                    succeeded=0,
                    failed=1,
                    results=[
                        ActivityBulkResultItem(
                            activityIndex=0,
                            activityId="activity-1",
                            status="NOK",
                            activity=None,
                            errors=ErrorResponse(
                                detail=[
                                    ErrorDetail(
                                        msg="bad",
                                        type="validation_error",
                                        loc=[],
                                    )
                                ]
                            ),
                        )
                    ],
                ),
            ]
        ),
    )
    created = await str_activities_bulk.post_activities_bulk(
        request,
        client=NamedClient(id="str-1", name="STR"),
        session=session,
    )
    partial = await str_activities_bulk.post_activities_bulk(
        request,
        client=NamedClient(id="str-1", name="STR"),
        session=session,
    )
    failed = await str_activities_bulk.post_activities_bulk(
        request,
        client=NamedClient(id="str-1", name="STR"),
        session=session,
    )
    assert created.status_code == 201
    assert partial.status_code == 200
    assert failed.status_code == 422


@pytest.mark.asyncio
async def test_str_areas_direct_branches(monkeypatch):
    session = cast("AsyncSession", object())
    monkeypatch.setattr(
        str_areas.area,
        "get_areas",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    area_id="area-1",
                    area_name="Area",
                    regulation="all",
                    filename="area.zip",
                    competent_authority_id_functional="ca-1",
                    competent_authority_name="CA",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        ),
    )
    areas = await str_areas.get_areas(session=session, offset=0, limit=None)
    assert areas.areas[0].area_id == "area-1"

    monkeypatch.setattr(str_areas.area, "count_areas", AsyncMock(return_value=7))
    count = await str_areas.count_areas(session=session)
    assert count.count == 7

    monkeypatch.setattr(str_areas.area, "get_area_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException, match="not found"):
        await str_areas.get_area("area-1", session=session)
    monkeypatch.setattr(
        str_areas.area,
        "get_area_by_id",
        AsyncMock(return_value=SimpleNamespace(filedata=b"zip", filename="shared.zip")),
    )
    area_response = await str_areas.get_area("area-1", session=session)
    assert (
        area_response.headers["content-disposition"]
        == 'attachment; filename="shared.zip"'
    )
