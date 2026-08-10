from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from app.crud import activity as activity_crud
from app.exceptions.business import InvalidOperationError
from app.schemas.error import ErrorDetail, ErrorResponse
from app.services import activity_bulk
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import ActivityFactory, AreaFactory, PlatformFactory


class _FakeValidationError(Exception):
    def errors(self):
        return []


class _FakeAdapter:
    def __init__(self, exception):
        self.exception = exception

    def validate_python(self, raw):
        raise self.exception


def _area(
    technical_id: int,
    area_name: str,
    competent_authority_id: str,
    competent_authority_name: str,
):
    return SimpleNamespace(
        id=technical_id,
        area_name=area_name,
        competent_authority=SimpleNamespace(
            competent_authority_id=competent_authority_id,
            competent_authority_name=competent_authority_name,
        ),
    )


@pytest.mark.asyncio
class TestActivityBulkService:
    async def test_create_activities_bulk_uses_string_fallback_for_empty_validation_errors(
        self, monkeypatch
    ):
        session = cast("AsyncSession", object())
        monkeypatch.setattr(activity_bulk, "ValidationError", _FakeValidationError)
        monkeypatch.setattr(
            activity_bulk,
            "_activity_request_adapter",
            _FakeAdapter(_FakeValidationError("broken payload")),
        )
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "get_by_client_id",
            AsyncMock(
                return_value=type(
                    "Platform", (), {"id": 1, "platform_name": "Platform"}
                )()
            ),
        )
        monkeypatch.setattr(
            activity_bulk.area_crud,
            "get_area_id_map",
            AsyncMock(return_value={}),
        )
        monkeypatch.setattr(activity_bulk.activity_crud, "bulk_create", AsyncMock())

        response = await activity_bulk.create_activities_bulk(
            session=session,
            activities_raw=[{"activityId": "a-1"}],
            client_id="platform-1",
            platform_name="Platform",
        )

        assert response.total_received == 1
        assert response.succeeded == 0
        assert response.failed == 1
        assert response.results[0].activity_id == "a-1"
        assert response.results[0].status == "NOK"
        assert response.results[0].errors == ErrorResponse(
            detail=[ErrorDetail(msg="broken payload", type="validation_error")]
        )

    async def test_create_activities_bulk_raises_for_deactivated_platform(
        self, monkeypatch
    ):
        session = cast("AsyncSession", object())
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "get_by_client_id",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "exists_any_by_client_id",
            AsyncMock(return_value=True),
        )

        with pytest.raises(InvalidOperationError, match="has been deactivated"):
            await activity_bulk.create_activities_bulk(
                session=session,
                activities_raw=[],
                client_id="platform-1",
                platform_name="Platform",
            )

    async def test_create_activities_bulk_versions_platform_and_rejects_deactivated_activity(
        self, monkeypatch
    ):
        session = cast("AsyncSession", object())
        platform = type(
            "Platform",
            (),
            {"id": 7, "platform_id": "platform-public-id", "platform_name": "Old name"},
        )()
        created_platform = type(
            "Platform",
            (),
            {"id": 8, "platform_id": "platform-public-id", "platform_name": "New name"},
        )()
        mark_as_ended = AsyncMock()
        bulk_create = AsyncMock()

        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "get_by_client_id",
            AsyncMock(return_value=platform),
        )
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "mark_as_ended_by_client_id",
            mark_as_ended,
        )
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "create",
            AsyncMock(return_value=created_platform),
        )
        monkeypatch.setattr(
            activity_bulk.area_crud,
            "get_area_ca_map",
            AsyncMock(
                return_value={
                    "area-1": _area(11, "Area 1", "ca-1", "CA 1"),
                    "area-2": _area(12, "Area 2", "ca-2", "CA 2"),
                }
            ),
        )
        monkeypatch.setattr(
            activity_bulk.activity_crud,
            "get_deactivated_activity_ids",
            AsyncMock(return_value={"activity-deactivated"}),
        )
        monkeypatch.setattr(
            activity_bulk.activity_crud,
            "bulk_mark_as_ended",
            AsyncMock(),
        )
        monkeypatch.setattr(activity_bulk.activity_crud, "bulk_create", bulk_create)

        activities_raw = [
            {
                "activityId": "activity-deactivated",
                "areaId": "area-1",
                "url": "http://example.com/1",
                "registrationNumber": "REG-1",
                "address": {
                    "thoroughfare": "Street",
                    "locatorDesignatorNumber": 1,
                    "postCode": "1234AB",
                    "postName": "City",
                    "fullAddress": "Street 1, 1234AB City",
                },
                "numberOfGuests": 1,
                "countryOfGuests": ["NLD"],
                "temporal": {
                    "startDatetime": "2025-06-01T14:00:00Z",
                    "endDatetime": "2025-06-07T11:00:00Z",
                },
            },
        ]

        response = await activity_bulk.create_activities_bulk(
            session=session,
            activities_raw=activities_raw,
            client_id="platform-1",
            platform_name="New name",
        )

        mark_as_ended.assert_awaited_once_with(session, "platform-1")
        bulk_create.assert_not_awaited()
        assert response.total_received == 1
        assert response.succeeded == 0
        assert response.failed == 1
        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        assert "deactivated" in response.results[0].errors.detail[0].msg

    async def test_create_activities_bulk_marks_missing_area_as_nok(self, monkeypatch):
        session = cast("AsyncSession", object())
        platform = type(
            "Platform",
            (),
            {"id": 3, "platform_id": "platform-public-id", "platform_name": "Platform"},
        )()
        bulk_create = AsyncMock()

        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "get_by_client_id",
            AsyncMock(return_value=platform),
        )
        monkeypatch.setattr(
            activity_bulk.area_crud,
            "get_area_ca_map",
            AsyncMock(
                return_value={"known-area": _area(9, "Known Area", "ca-1", "CA 1")}
            ),
        )
        monkeypatch.setattr(
            activity_bulk.activity_crud,
            "get_deactivated_activity_ids",
            AsyncMock(return_value=set()),
        )
        monkeypatch.setattr(
            activity_bulk.activity_crud,
            "get_current_by_activity_ids",
            AsyncMock(return_value=set()),
        )
        monkeypatch.setattr(
            activity_bulk.activity_crud, "bulk_mark_as_ended", AsyncMock()
        )
        monkeypatch.setattr(activity_bulk.activity_crud, "bulk_create", bulk_create)

        response = await activity_bulk.create_activities_bulk(
            session=session,
            activities_raw=[
                {
                    "activityId": "activity-1",
                    "areaId": "unknown-area",
                    "url": "http://example.com/1",
                    "registrationNumber": "REG-1",
                    "address": {
                        "thoroughfare": "Street",
                        "locatorDesignatorNumber": 1,
                        "postCode": "1234AB",
                        "postName": "City",
                        "fullAddress": "Street 1, 1234AB City",
                    },
                    "numberOfGuests": 1,
                    "countryOfGuests": ["NLD"],
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                }
            ],
            client_id="platform-1",
            platform_name="Platform",
        )

        bulk_create.assert_not_awaited()
        assert response.succeeded == 0
        assert response.failed == 1
        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        assert "not found" in response.results[0].errors.detail[0].msg

    @pytest.mark.database
    async def test_create_activities_bulk_creates_platform_and_marks_duplicate_nok(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(
            async_session,
            area_id="service-area-1",
            area_name="Service Area",
            competent_authority_id="service-ca",
            competent_authority_name="Service CA",
        )

        response = await activity_bulk.create_activities_bulk(
            session=async_session,
            activities_raw=[
                {
                    "activityId": "service-duplicate",
                    "areaId": area.area_id,
                    "url": "http://example.com/service-duplicate-1",
                    "registrationNumber": "REG-SVC-1",
                    "address": {
                        "thoroughfare": "Street",
                        "locatorDesignatorNumber": 1,
                        "postCode": "1234AB",
                        "postName": "City",
                        "fullAddress": "Street 1, 1234AB City",
                    },
                    "numberOfGuests": 1,
                    "countryOfGuests": ["NLD"],
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                {
                    "activityId": "service-duplicate",
                    "areaId": area.area_id,
                    "url": "http://example.com/service-duplicate-2",
                    "registrationNumber": "REG-SVC-2",
                    "address": {
                        "thoroughfare": "Street",
                        "locatorDesignatorNumber": 2,
                        "postCode": "1234AB",
                        "postName": "City",
                        "fullAddress": "Street 2, 1234AB City",
                    },
                    "numberOfGuests": 1,
                    "countryOfGuests": ["DEU"],
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
            ],
            client_id="service-platform",
            platform_name="Service Platform",
        )

        assert response.succeeded == 1
        assert response.failed == 1
        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        assert "Superseded by later item" in response.results[0].errors.detail[0].msg
        assert response.results[1].status == "OK"
        assert response.results[1].activity is not None
        assert response.results[1].activity.area_name == "Service Area"
        assert response.results[1].activity.platform_name == "Service Platform"

    @pytest.mark.database
    async def test_create_activities_bulk_versions_existing_activity(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="version-area")
        platform = await PlatformFactory.create_async(
            async_session,
            platform_id="version-platform",
            client_id="version-client",
            platform_name="Version Platform",
        )
        existing = await ActivityFactory.create_async(
            async_session,
            activity_id="service-versioned",
            platform_id=platform.id,
            area_id=area.id,
        )

        response = await activity_bulk.create_activities_bulk(
            session=async_session,
            activities_raw=[
                {
                    "activityId": existing.activity_id,
                    "areaId": area.area_id,
                    "url": "http://example.com/service-versioned",
                    "registrationNumber": "REG-SVC-V",
                    "address": {
                        "thoroughfare": "Street",
                        "locatorDesignatorNumber": 3,
                        "postCode": "1234AB",
                        "postName": "City",
                        "fullAddress": "Street 3, 1234AB City",
                    },
                    "numberOfGuests": 1,
                    "countryOfGuests": ["BEL"],
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                }
            ],
            client_id=platform.client_id,
            platform_name=platform.platform_name or "",
        )

        assert response.succeeded == 1
        assert response.failed == 0
        assert response.results[0].status == "OK"
        versions = [
            record
            for record in await activity_crud.get_all(async_session)
            if record.activity_id == existing.activity_id
        ]
        assert len(versions) == 2
        assert sum(1 for record in versions if record.ended_at is None) == 1
        assert sum(1 for record in versions if record.ended_at is not None) == 1

    @pytest.mark.database
    async def test_create_activities_bulk_rejects_deactivated_and_keeps_valid_item(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="mixed-area")
        platform = await PlatformFactory.create_async(
            async_session,
            platform_id="mixed-platform",
            client_id="mixed-client",
            platform_name="Mixed Platform",
        )
        ended = await ActivityFactory.create_async(
            async_session,
            activity_id="mixed-ended",
            platform_id=platform.id,
            area_id=area.id,
        )
        await activity_crud.mark_as_ended(async_session, ended.activity_id, platform.id)

        response = await activity_bulk.create_activities_bulk(
            session=async_session,
            activities_raw=[
                {
                    "activityId": ended.activity_id,
                    "areaId": area.area_id,
                    "url": "http://example.com/mixed-ended",
                    "registrationNumber": "REG-MIX-1",
                    "address": {
                        "thoroughfare": "Street",
                        "locatorDesignatorNumber": 4,
                        "postCode": "1234AB",
                        "postName": "City",
                        "fullAddress": "Street 4, 1234AB City",
                    },
                    "numberOfGuests": 1,
                    "countryOfGuests": ["NLD"],
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
                {
                    "activityId": "mixed-valid",
                    "areaId": area.area_id,
                    "url": "http://example.com/mixed-valid",
                    "registrationNumber": "REG-MIX-2",
                    "address": {
                        "thoroughfare": "Street",
                        "locatorDesignatorNumber": 5,
                        "postCode": "1234AB",
                        "postName": "City",
                        "fullAddress": "Street 5, 1234AB City",
                    },
                    "numberOfGuests": 1,
                    "countryOfGuests": ["DEU"],
                    "temporal": {
                        "startDatetime": "2025-06-01T14:00:00Z",
                        "endDatetime": "2025-06-07T11:00:00Z",
                    },
                },
            ],
            client_id=platform.client_id,
            platform_name=platform.platform_name or "",
        )

        assert response.succeeded == 1
        assert response.failed == 1
        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        assert "deactivated" in response.results[0].errors.detail[0].msg
        assert response.results[1].status == "OK"
