from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest
from app.exceptions.business import InvalidOperationError
from app.schemas.error import ErrorDetail, ErrorResponse
from app.services import activity_bulk

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _FakeValidationError(Exception):
    def errors(self):
        return []


class _FakeAdapter:
    def __init__(self, exception):
        self.exception = exception

    def validate_python(self, raw):
        raise self.exception


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

    async def test_create_activities_bulk_versions_platform_and_deactivated_activity(
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
        bulk_mark_as_ended = AsyncMock()
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
                    "area-1": (11, "ca-1", "CA 1"),
                    "area-2": (12, "ca-2", "CA 2"),
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
            "get_current_by_activity_ids",
            AsyncMock(return_value={"activity-current"}),
        )
        monkeypatch.setattr(
            activity_bulk.activity_crud,
            "bulk_mark_as_ended",
            bulk_mark_as_ended,
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
            {
                "activityId": "activity-current",
                "areaId": "area-2",
                "url": "http://example.com/2",
                "registrationNumber": "REG-2",
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
        ]

        response = await activity_bulk.create_activities_bulk(
            session=session,
            activities_raw=activities_raw,
            client_id="platform-1",
            platform_name="New name",
        )

        mark_as_ended.assert_awaited_once_with(session, "platform-1")
        bulk_mark_as_ended.assert_awaited_once_with(session, ["activity-current"], 8)
        bulk_create.assert_awaited_once()
        assert response.total_received == 2
        assert response.succeeded == 1
        assert response.failed == 1
        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        assert "deactivated" in response.results[0].errors.detail[0].msg
        assert response.results[1].status == "OK"
        assert response.results[1].activity_id == "activity-current"

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
            AsyncMock(return_value={"known-area": (9, "ca-1", "CA 1")}),
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

    async def test_create_activities_bulk_creates_platform_and_marks_earlier_duplicate_nok(
        self, monkeypatch
    ):
        session = cast("AsyncSession", object())
        created_platform = type(
            "Platform",
            (),
            {"id": 4, "platform_id": "platform-public-id", "platform_name": "Platform"},
        )()
        bulk_create = AsyncMock()

        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "get_by_client_id",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "exists_any_by_client_id",
            AsyncMock(return_value=False),
        )
        monkeypatch.setattr(
            activity_bulk.platform_crud,
            "create",
            AsyncMock(return_value=created_platform),
        )
        monkeypatch.setattr(
            activity_bulk.area_crud,
            "get_area_ca_map",
            AsyncMock(return_value={"area-1": (11, "ca-1", "CA 1")}),
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
                    "activityId": "same-id",
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
                {
                    "activityId": "same-id",
                    "areaId": "area-1",
                    "url": "http://example.com/2",
                    "registrationNumber": "REG-2",
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
            client_id="platform-1",
            platform_name="Platform",
        )

        bulk_create.assert_awaited_once()
        assert response.succeeded == 1
        assert response.failed == 1
        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        assert "Superseded by later item" in response.results[0].errors.detail[0].msg
        assert response.results[1].status == "OK"
