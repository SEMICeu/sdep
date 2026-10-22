import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from app.crud import activity as activity_crud
from app.crud import platform as platform_crud
from app.enums import Regulation
from app.exceptions.business import InvalidOperationError
from app.exceptions.handlers import is_unique_violation
from app.models.activity import Activity
from app.schemas.error import ErrorDetail, ErrorResponse
from app.services import activity_bulk
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
        regulation=Regulation.all,
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
        fake_adapter = _FakeAdapter(_FakeValidationError("broken payload"))
        monkeypatch.setattr(activity_bulk, "_ITEM_ADAPTER", fake_adapter)
        monkeypatch.setattr(
            platform_crud,
            "get_by_client_id",
            AsyncMock(
                return_value=type(
                    "Platform",
                    (),
                    {"id": 1, "platform_id": "p-1", "platform_name": "Platform"},
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
            platform_crud,
            "get_by_client_id",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            platform_crud,
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
            platform_crud,
            "get_by_client_id",
            AsyncMock(return_value=platform),
        )
        monkeypatch.setattr(
            platform_crud,
            "mark_as_ended_by_client_id",
            mark_as_ended,
        )
        monkeypatch.setattr(
            platform_crud,
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
        monkeypatch.setattr(activity_bulk.identity_crud, "lock_client", AsyncMock())
        monkeypatch.setattr(
            activity_bulk.identity_crud,
            "claim",
            AsyncMock(side_effect=lambda _s, _m, ids, owner: dict.fromkeys(ids, owner)),
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
            platform_crud,
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
        await activity_crud.mark_as_ended(
            async_session, ended.activity_id, platform.platform_id
        )

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


@pytest.mark.asyncio
async def test_create_activities_bulk_rejects_listing_only_area(
    monkeypatch,
):
    """The regulation check marks the item NOK instead of 'not found'."""
    session = cast("AsyncSession", object())
    listing_area = SimpleNamespace(id=1, regulation=Regulation.listing)
    monkeypatch.setattr(
        platform_crud,
        "get_by_client_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=1, platform_id="p-1", platform_name="Platform"
            )
        ),
    )
    monkeypatch.setattr(
        activity_bulk.area_crud,
        "get_area_ca_map",
        AsyncMock(return_value={"area-listing": listing_area}),
    )
    bulk_create = AsyncMock()
    monkeypatch.setattr(activity_bulk.activity_crud, "bulk_create", bulk_create)

    response = await activity_bulk.create_activities_bulk(
        session=session,
        activities_raw=[
            {
                "activityId": "a-1",
                "areaId": "area-listing",
                "url": "http://example.com/1",
                "address": {
                    "thoroughfare": "T",
                    "postCode": "1234AB",
                    "postName": "P",
                    "fullAddress": "T 1, 1234AB P",
                },
                "registrationNumber": "REG",
                "numberOfGuests": 1,
                "countryOfGuests": ["NLD"],
                "temporal": {
                    "startDatetime": "2025-06-01T14:00:00Z",
                    "endDatetime": "2025-06-02T11:00:00Z",
                },
            }
        ],
        client_id="platform-1",
        platform_name="Platform",
    )

    assert response.failed == 1
    assert response.results[0].errors == ErrorResponse(
        detail=[
            ErrorDetail(
                msg="Area with areaId 'area-listing' is regulated for listing only",
                type="regulation_error",
                loc=["areaId"],
            )
        ]
    )
    bulk_create.assert_not_awaited()


def _activity(activity_id: str, area_id: str) -> dict:
    return {
        "activityId": activity_id,
        "areaId": area_id,
        "url": f"http://example.com/{activity_id}",
        "registrationNumber": "REG-1",
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
    }


async def _current_count(session: AsyncSession, activity_id: str) -> int:
    rows = await session.execute(
        select(Activity).where(
            Activity.activity_id == activity_id, Activity.ended_at.is_(None)
        )
    )
    return len(rows.scalars().all())


@pytest.mark.database
@pytest.mark.asyncio
class TestActivityVersioningAcrossPlatforms:
    async def test_resubmit_after_platform_rename_keeps_one_current_version(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="rename-area")
        # Backdated, so the rename's new platform version gets another created_at
        await PlatformFactory.create_async(
            async_session,
            client_id="str-1",
            platform_name="STR 1",
            created_at=datetime(2026, 1, 1),
        )
        for name in ("STR 1", "STR 1 renamed"):
            response = await activity_bulk.create_activities_bulk(
                async_session, [_activity("a-1", area.area_id)], "str-1", name
            )
            assert response.results[0].status == "OK", response.results[0]
        assert await _current_count(async_session, "a-1") == 1

    async def test_activity_id_of_another_platform_is_refused(
        self, async_session: AsyncSession
    ):
        """An activityId has one owner, also after its activity ended."""
        area = await AreaFactory.create_async(async_session, area_id="guard-area")
        other = await PlatformFactory.create_async(
            async_session, platform_id="p-other", client_id="str-other"
        )
        await ActivityFactory.create_async(
            async_session,
            activity_id="a-current",
            platform_id=other.id,
            area_id=area.id,
        )
        ended = await ActivityFactory.create_async(
            async_session, activity_id="a-ended", platform_id=other.id, area_id=area.id
        )
        await activity_crud.mark_as_ended(
            async_session, ended.activity_id, other.platform_id
        )

        response = await activity_bulk.create_activities_bulk(
            async_session,
            [_activity("a-current", area.area_id), _activity("a-ended", area.area_id)],
            "str-1",
            "STR 1",
        )

        for result in response.results:
            assert result.status == "NOK", result
            assert result.errors is not None
            assert result.errors.detail[0].type == "duplicate_error"
        assert await _current_count(async_session, "a-current") == 1
        assert await _current_count(async_session, "a-ended") == 0

    async def test_activity_id_is_case_sensitive(self, async_session: AsyncSession):
        """`A-Case` and `a-case` are two activityIds, so two owners can each have one."""
        area = await AreaFactory.create_async(async_session, area_id="case-area")

        first = await activity_bulk.create_activities_bulk(
            async_session, [_activity("A-Case", area.area_id)], "str-1", "STR 1"
        )
        second = await activity_bulk.create_activities_bulk(
            async_session, [_activity("a-case", area.area_id)], "str-2", "STR 2"
        )

        assert [r.status for r in (*first.results, *second.results)] == ["OK", "OK"]
        assert await _current_count(async_session, "A-Case") == 1
        assert await _current_count(async_session, "a-case") == 1

    async def test_non_object_item_is_nok_not_500(self, async_session: AsyncSession):
        response = await activity_bulk.create_activities_bulk(
            async_session, cast("list[dict]", [123]), "str-1", "STR 1"
        )
        assert response.failed == 1
        assert response.results[0].activity_id is None

    async def test_non_string_activity_id_is_nok_not_500(
        self, async_session: AsyncSession
    ):
        """A non-string activityId is NOK and echoed as null, a string as supplied."""
        response = await activity_bulk.create_activities_bulk(
            async_session,
            [{"activityId": 123}, {"activityId": ["x"]}, {"activityId": "bad/id"}],
            "str-1",
            "STR 1",
        )
        assert response.failed == 3
        assert [r.activity_id for r in response.results] == [None, None, "bad/id"]
        assert response.results[0].errors is not None
        assert "activityId" in {
            loc for d in response.results[0].errors.detail for loc in d.loc or []
        }

    async def test_second_current_version_is_refused_by_the_database(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="race-area")
        platform = await PlatformFactory.create_async(async_session)
        await ActivityFactory.create_async(
            async_session,
            activity_id="a-race",
            platform_id=platform.id,
            area_id=area.id,
        )
        # What a lost race inserts: a second current row for the same key
        with pytest.raises(IntegrityError) as exc:
            await ActivityFactory.create_async(
                async_session,
                activity_id="a-race",
                platform_id=platform.id,
                area_id=area.id,
            )
        assert is_unique_violation(exc.value)


async def _version_count(session: AsyncSession, activity_id: str) -> int:
    rows = await session.execute(
        select(Activity).where(Activity.activity_id == activity_id)
    )
    return len(rows.scalars().all())


def _without_id(area_id: str, **overrides) -> dict:
    item = _activity("unused", area_id)
    del item["activityId"]
    item.update(overrides)
    return item


@pytest.mark.database
@pytest.mark.asyncio
class TestGeneratedActivityId:
    """An identical activity is a resend, with or without activityId (no new version)."""

    async def _post(self, session: AsyncSession, items: list[dict], client="str-1"):
        return await activity_bulk.create_activities_bulk(
            session, items, client, client.upper()
        )

    async def test_resend_returns_the_stored_activity(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="gen-area")
        first = await self._post(async_session, [_without_id(area.area_id)])
        # Same activity, other notation: `+00:00` for `Z`, the default status spelled out
        resent = _without_id(area.area_id, status="finished")
        resent["temporal"] = {
            "startDatetime": "2025-06-01T14:00:00+00:00",
            "endDatetime": "2025-06-07T11:00:00+00:00",
        }
        second = await self._post(async_session, [resent])

        stored, again = first.results[0].activity, second.results[0].activity
        assert stored is not None and again is not None
        assert second.results[0].status == "OK"
        assert second.results[0].activity_id is None  # nothing supplied
        assert again.activity_id == stored.activity_id
        # SQLite reads timestamps back without a time zone
        assert again.created_at.replace(tzinfo=None) == stored.created_at.replace(
            tzinfo=None
        )
        assert uuid.UUID(stored.activity_id).version == 8
        assert await _version_count(async_session, stored.activity_id) == 1

    async def test_other_content_or_platform_gives_another_activity(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="gen-area-2")
        base = await self._post(async_session, [_without_id(area.area_id)])
        changed = await self._post(
            async_session,
            [
                _without_id(
                    area.area_id, numberOfGuests=2, countryOfGuests=["NLD", "NLD"]
                )
            ],
        )
        other = await self._post(async_session, [_without_id(area.area_id)], "str-2")

        ids = {
            r.results[0].activity.activity_id
            for r in (base, changed, other)
            if r.results[0].activity is not None
        }
        assert len(ids) == 3

    async def test_two_identical_items_in_one_batch_last_wins(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="gen-area-3")
        response = await self._post(
            async_session, [_without_id(area.area_id), _without_id(area.area_id)]
        )
        assert [r.status for r in response.results] == ["NOK", "OK"]
        assert response.results[0].errors is not None
        assert response.results[0].errors.detail[0].type == "duplicate_error"

    async def test_deactivated_activity_is_new_again(self, async_session: AsyncSession):
        area = await AreaFactory.create_async(async_session, area_id="gen-area-4")
        first = await self._post(async_session, [_without_id(area.area_id)])
        old = first.results[0].activity
        assert old is not None
        await activity_crud.mark_as_ended(
            async_session, old.activity_id, old.platform_id
        )

        second = await self._post(async_session, [_without_id(area.area_id)])
        third = await self._post(async_session, [_without_id(area.area_id)])

        new, again = second.results[0].activity, third.results[0].activity
        assert new is not None and again is not None
        assert new.activity_id != old.activity_id
        assert again.activity_id == new.activity_id
        assert await _version_count(async_session, new.activity_id) == 1

    async def test_identical_activity_with_its_id_is_a_resend(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="gen-area-5")
        first = await self._post(async_session, [_activity("own-id", area.area_id)])
        # Same activity, other notation: `+00:00` for `Z`, the default status spelled out
        resent = _activity("own-id", area.area_id) | {"status": "finished"}
        resent["temporal"] = {
            "startDatetime": "2025-06-01T14:00:00+00:00",
            "endDatetime": "2025-06-07T11:00:00+00:00",
        }
        second = await self._post(async_session, [resent])

        stored, again = first.results[0].activity, second.results[0].activity
        assert stored is not None and again is not None
        assert second.results[0].status == "OK"
        assert again.created_at.replace(tzinfo=None) == stored.created_at.replace(
            tzinfo=None
        )
        assert await _version_count(async_session, "own-id") == 1

    @pytest.mark.parametrize(
        "empty", [None, "", "    "], ids=["null", "empty", "spaces"]
    )
    @pytest.mark.parametrize(
        "activity_id", [None, "own-null"], ids=["generated", "own"]
    )
    async def test_null_or_empty_equals_an_omitted_field(
        self, async_session: AsyncSession, activity_id: str | None, empty: str | None
    ):
        """An optional field sent as null, "" or spaces is the same content as omitted."""
        area = await AreaFactory.create_async(async_session, area_id="gen-area-7")
        first = _without_id(area.area_id)
        resent = _without_id(area.area_id, activityName=empty)
        resent["address"] = resent["address"] | {
            "locatorDesignatorLetter": empty,
            "locatorDesignatorAddition": empty,
        }
        if activity_id is not None:
            first["activityId"] = resent["activityId"] = activity_id
        stored = (await self._post(async_session, [first])).results[0].activity
        again = (await self._post(async_session, [resent])).results[0].activity

        assert stored is not None and again is not None
        assert again.activity_id == stored.activity_id
        assert await _version_count(async_session, stored.activity_id) == 1

    @pytest.mark.parametrize(
        "activity_id", [None, "own-trim"], ids=["generated", "own"]
    )
    async def test_surrounding_spaces_are_trimmed(
        self, async_session: AsyncSession, activity_id: str | None
    ):
        """ " Name " is the same content as "Name", and is stored as "Name"."""
        area = await AreaFactory.create_async(async_session, area_id="gen-area-8")
        first = _without_id(area.area_id, activityName="Name")
        resent = _without_id(area.area_id, activityName=" Name ")
        if activity_id is not None:
            first["activityId"] = resent["activityId"] = activity_id
        stored = (await self._post(async_session, [first])).results[0].activity
        again = (await self._post(async_session, [resent])).results[0].activity

        assert stored is not None and again is not None
        assert again.activity_id == stored.activity_id
        assert again.activity_name == "Name"
        assert await _version_count(async_session, stored.activity_id) == 1

    async def test_changed_activity_with_its_id_versions(
        self, async_session: AsyncSession
    ):
        area = await AreaFactory.create_async(async_session, area_id="gen-area-6")
        await self._post(async_session, [_activity("own-id-2", area.area_id)])
        changed = _activity("own-id-2", area.area_id) | {"status": "cancelled"}
        response = await self._post(async_session, [changed])

        assert response.results[0].activity is not None
        assert response.results[0].activity.status == "cancelled"
        assert await _version_count(async_session, "own-id-2") == 2
        assert await _current_count(async_session, "own-id-2") == 1
