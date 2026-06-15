from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest
from app.api.common import activity_handlers
from app.api.common.auth_dependencies import Client, NamedClient
from app.api.common.pagination import PaginationParams
from app.api.common.routers import str_activities_bulk, str_areas
from app.api.domains.ca.routers import activities_v1 as ca_activities
from app.api.domains.ca.routers import areas as ca_areas
from app.api.domains.rep.routers import activities_v1 as rep_activities
from app.models.address import Address
from app.models.temporal import Temporal
from app.schemas.activity import ActivityFilters
from app.schemas.activity_bulk import (
    ActivityBulkRequest,
    ActivityBulkResponse,
    ActivityBulkResultItem,
)
from app.schemas.error import ErrorDetail, ErrorResponse
from app.security.malware_scan import ScanResult
from fastapi import HTTPException, Request, UploadFile

from tests.api.zip_stub import ZIP

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _stub_request(headers: dict[str, str] | None = None) -> Request:
    """Minimal Request stub for direct router calls — only `.headers.get(...)` is exercised."""
    return cast("Request", SimpleNamespace(headers=headers or {}))


@pytest.mark.asyncio
async def test_ca_activities_direct_branches(monkeypatch):
    session = cast("AsyncSession", object())
    monkeypatch.setattr(
        activity_handlers.activity,
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
        pagination=PaginationParams(offset=0, limit=None),
        session=session,
    )
    assert result.activities[0].activity_id == "activity-1"

    monkeypatch.setattr(
        activity_handlers.activity,
        "count_current_activities",
        AsyncMock(return_value=5),
    )
    count = await ca_activities.count_activities(
        client=Client(id="ca-1", name="CA"), session=session
    )
    assert count.count == 5


@pytest.mark.asyncio
async def test_rep_activities_direct_branches(monkeypatch):
    session = cast("AsyncSession", object())
    monkeypatch.setattr(
        activity_handlers.activity,
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
    result = await rep_activities.get_activities(
        pagination=PaginationParams(offset=0, limit=None),
        filters=ActivityFilters(),
        session=session,
    )
    assert result.activities[0].activity_id == "activity-1"

    monkeypatch.setattr(
        activity_handlers.activity,
        "count_current_activities",
        AsyncMock(return_value=5),
    )
    count = await rep_activities.count_activities(
        filters=ActivityFilters(), session=session
    )
    assert count.count == 5


@pytest.mark.asyncio
async def test_ca_areas_direct_branches(monkeypatch):
    session = cast("AsyncSession", object())

    async def clean_scan(filedata: bytes) -> ScanResult:
        return ScanResult(
            passed_malware_scan=True,
            message="mocked clean file",
        )

    monkeypatch.setattr(
        ca_areas,
        "scan_file_for_malware",
        clean_scan,
    )

    with pytest.raises(HTTPException, match="at most 64 characters"):
        await ca_areas.post_area(
            request=_stub_request(),
            client=NamedClient(id="ca-1", name="CA"),
            session=session,
            areaId=None,
            areaName="x" * 65,
            regulation=None,
            file=UploadFile(filename="area.zip", file=io.BytesIO(ZIP)),
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
                competent_authority=SimpleNamespace(
                    competent_authority_id="ca-public-id",
                    competent_authority_name="CA",
                ),
                created_at="2025-01-01T00:00:00Z",
            )
        ),
    )
    created = await ca_areas.post_area(
        request=_stub_request(),
        client=NamedClient(id="ca-1", name="CA"),
        session=session,
        areaId=None,
        areaName=None,
        regulation=None,
        file=UploadFile(filename="area.zip", file=io.BytesIO(ZIP)),
    )
    assert json.loads(bytes(created.body))["areaId"] == "area-1"

    monkeypatch.setattr(ca_areas, "sanitize_upload_filename", lambda raw: ".zip")
    with pytest.raises(HTTPException, match=r"must contain a name before the \.zip"):
        await ca_areas.post_area(
            request=_stub_request(),
            client=NamedClient(id="ca-1", name="CA"),
            session=session,
            areaId=None,
            areaName=None,
            regulation=None,
            file=UploadFile(filename=".zip", file=io.BytesIO(ZIP)),
        )
    monkeypatch.undo()

    async def rejected_scan(filedata: bytes) -> ScanResult:
        return ScanResult(passed_malware_scan=False, message="malware")

    monkeypatch.setattr(
        ca_areas,
        "scan_file_for_malware",
        rejected_scan,
    )
    with pytest.raises(HTTPException, match="may contain malicious content"):
        await ca_areas.post_area(
            request=_stub_request(),
            client=NamedClient(id="ca-1", name="CA"),
            session=session,
            areaId=None,
            areaName=None,
            regulation=None,
            file=UploadFile(filename="area.zip", file=io.BytesIO(b"data")),
        )

    # Content-Length fail-fast: advertised size above the envelope cap → 413
    oversize = ca_areas.MAX_REQUEST_SIZE + 1
    with pytest.raises(HTTPException) as oversize_exc:
        await ca_areas.post_area(
            request=_stub_request(headers={"content-length": str(oversize)}),
            client=NamedClient(id="ca-1", name="CA"),
            session=session,
            areaId=None,
            areaName=None,
            regulation=None,
            file=UploadFile(filename="area.zip", file=io.BytesIO(ZIP)),
        )
    assert oversize_exc.value.status_code == 413

    # Malformed Content-Length is ignored (falls through to body-length check);
    # the rest of the validation pipeline still runs.
    with pytest.raises(HTTPException, match="may contain malicious content"):
        await ca_areas.post_area(
            request=_stub_request(headers={"content-length": "not-a-number"}),
            client=NamedClient(id="ca-1", name="CA"),
            session=session,
            areaId=None,
            areaName=None,
            regulation=None,
            file=UploadFile(filename="area.zip", file=io.BytesIO(b"data")),
        )

    monkeypatch.setattr(
        ca_areas.area_service,
        "get_areas_by_client_id",
        AsyncMock(
            return_value=[
                SimpleNamespace(
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
            ]
        ),
    )
    own_areas = await ca_areas.get_own_areas(
        client=Client(id="ca-1", name="CA"),
        pagination=PaginationParams(offset=0, limit=None),
        session=session,
    )
    assert json.loads(bytes(own_areas.body))["areas"][0]["areaId"] == "area-1"

    monkeypatch.setattr(
        ca_areas.area_service,
        "count_areas_by_client_id",
        AsyncMock(return_value=2),
    )
    count = await ca_areas.count_own_areas(
        client=Client(id="ca-1", name="CA"), session=session
    )
    assert count.count == 2

    monkeypatch.setattr(
        ca_areas.area_service,
        "get_area_by_area_id_and_client_id",
        AsyncMock(return_value=None),
    )
    with pytest.raises(HTTPException, match="not found"):
        await ca_areas.get_own_area(
            client=Client(id="ca-1", name="CA"), areaId="area-1", session=session
        )
    monkeypatch.setattr(
        ca_areas.area_service,
        "get_area_by_area_id_and_client_id",
        AsyncMock(
            return_value=SimpleNamespace(filedata=b"zipdata", filename="owned.zip")
        ),
    )
    response = await ca_areas.get_own_area(
        client=Client(id="ca-1", name="CA"), areaId="area-1", session=session
    )
    assert 'filename="owned.zip"' in response.headers["content-disposition"]
    assert "filename*=UTF-8''owned.zip" in response.headers["content-disposition"]

    monkeypatch.setattr(ca_areas.area_service, "delete_area_by_client_id", AsyncMock())
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
                    competent_authority=SimpleNamespace(
                        competent_authority_id="ca-1",
                        competent_authority_name="CA",
                    ),
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        ),
    )
    areas = await str_areas.get_areas(
        pagination=PaginationParams(offset=0, limit=None),
        session=session,
    )
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
    assert 'filename="shared.zip"' in area_response.headers["content-disposition"]
    assert "filename*=UTF-8''shared.zip" in area_response.headers["content-disposition"]
