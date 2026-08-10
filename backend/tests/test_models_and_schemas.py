from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.enums import ActivityStatus, Regulation
from app.models.activity import Activity
from app.models.address import Address
from app.models.area import Area
from app.models.competent_authority import CompetentAuthority
from app.models.platform import Platform
from app.models.temporal import Temporal
from app.models.types import StringArray
from app.schemas.activity import ActivityRequest, ActivityResponse
from app.schemas.activity import (
    empty_string_to_none as activity_empty_string_to_none,
)
from app.schemas.address import CommonAddressRequest
from app.schemas.area import AreaResponse
from app.schemas.area import (
    empty_string_to_none as area_empty_string_to_none,
)
from app.schemas.temporal import CommonTemporalRequest, validate_year_ge_2025
from sqlalchemy import CheckConstraint, Table


def test_activity_and_area_models_include_documented_check_constraints():
    activity_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in cast("Table", Activity.__table__).constraints
        if isinstance(constraint, CheckConstraint)
    }
    area_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in cast("Table", Area.__table__).constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert activity_checks["ck_activity_temporal_start_before_end"] == (
        "temporal_start_date_time < temporal_end_date_time"
    )
    assert activity_checks["ck_activity_temporal_start_year_ge_2025"] == (
        "EXTRACT(YEAR FROM temporal_start_date_time) >= 2025"
    )
    assert activity_checks["ck_activity_address_locator_designator_letter_alpha"] == (
        "address_locator_designator_letter IS NULL OR "
        "address_locator_designator_letter ~ '^[A-Za-z]+$'"
    )
    assert activity_checks["ck_activity_activity_id_format"] == (
        "activity_id ~ '^[A-Za-z0-9-]+$'"
    )
    assert area_checks["ck_area_area_id_format"] == ("area_id ~ '^[A-Za-z0-9-]+$'")


def test_address_and_temporal_model_helpers_cover_repr_eq_and_validation():
    address = Address("Street", 1, "A", "2", "1234AB", "City", "Street 1")
    same = Address("Street", 1, "A", "2", "1234AB", "City", "Street 1")
    other = Address("Other", 2, None, None, "9999ZZ", "Town", "Other 2")

    assert address.__composite_values__() == (
        "Street",
        1,
        "A",
        "2",
        "1234AB",
        "City",
        "Street 1",
    )
    assert "Street" in repr(address)
    assert address == same
    assert address != other
    assert address != object()

    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 2, tzinfo=UTC)
    temporal = Temporal(start, end)
    assert temporal.__composite_values__() == (start, end)
    assert temporal.is_valid is True
    assert temporal == Temporal(start, end)
    assert temporal != Temporal(start, datetime(2025, 1, 3, tzinfo=UTC))
    assert temporal != object()
    assert "start_date_time" in repr(temporal)

    with pytest.raises(ValueError, match="year must be >= 2025"):
        Temporal(datetime(2024, 1, 1, tzinfo=UTC), end)
    with pytest.raises(ValueError, match="must be less than end_date_time"):
        Temporal(end, end)


def test_string_array_type_covers_supported_and_unsupported_dialects():
    type_ = StringArray()
    sqlite = cast(
        "Any", SimpleNamespace(name="sqlite", type_descriptor=lambda value: value)
    )
    postgres = cast(
        "Any", SimpleNamespace(name="postgresql", type_descriptor=lambda value: value)
    )
    unsupported = cast(
        "Any", SimpleNamespace(name="oracle", type_descriptor=lambda value: value)
    )

    assert type_.load_dialect_impl(sqlite).__class__.__name__ == "Text"
    assert type_.load_dialect_impl(postgres).__class__.__name__ == "ARRAY"
    assert type_.process_bind_param(["NLD"], postgres) == ["NLD"]
    assert type_.process_bind_param(["NLD"], sqlite) == '["NLD"]'
    assert type_.process_result_value('["NLD"]', sqlite) == ["NLD"]
    assert type_.process_result_value(["NLD"], postgres) == ["NLD"]
    assert type_.process_bind_param(None, sqlite) is None
    assert type_.process_result_value(None, sqlite) is None

    with pytest.raises(NotImplementedError):
        type_.load_dialect_impl(unsupported)
    with pytest.raises(NotImplementedError):
        type_.process_bind_param(["NLD"], unsupported)
    with pytest.raises(NotImplementedError):
        type_.process_result_value('["NLD"]', unsupported)


def test_model_repr_methods_and_defaults_cover_remaining_model_lines():
    activity = Activity()
    area = Area()
    platform = Platform(platform_id="platform-1", platform_name="Platform")
    ca = CompetentAuthority(
        competent_authority_id="ca-1", competent_authority_name="Authority"
    )

    activity.activity_id = "activity-1"
    area.id = 1
    area.area_id = "area-1"
    area.filename = "area.zip"
    platform.id = 1
    ca.id = 1

    assert isinstance(activity.activity_id, str)
    assert activity.id is None
    assert "area-1" in repr(area)
    assert area.activities == []
    assert "platform-1" in repr(platform)
    assert "ca-1" in repr(ca)


def test_activity_and_area_schema_helpers_and_serializers():
    assert activity_empty_string_to_none("") is None
    assert activity_empty_string_to_none("abc") == "abc"
    assert area_empty_string_to_none("") is None
    assert area_empty_string_to_none("listing") == "listing"

    with pytest.raises(ValueError, match="must not contain spaces"):
        CommonAddressRequest.validate_post_code_format("12 34")
    with pytest.raises(ValueError, match="must be alphanumeric"):
        CommonAddressRequest.validate_post_code_format("12-34")
    assert (
        CommonAddressRequest.validate_locator_designator_letter_is_alphabetic("AB")
        == "AB"
    )
    with pytest.raises(ValueError, match="only alphabetic characters"):
        CommonAddressRequest.validate_locator_designator_letter_is_alphabetic("A1")
    with pytest.raises(ValueError, match="not a valid ISO 3166-1 alpha-3"):
        ActivityRequest.model_validate(
            {
                "activityId": "activity-1",
                "activityName": None,
                "status": "finished",
                "areaId": "area-1",
                "url": "http://example.com",
                "address": {
                    "thoroughfare": "Street",
                    "locatorDesignatorNumber": 1,
                    "postCode": "1234AB",
                    "postName": "City",
                    "fullAddress": "Street 1, 1234AB City",
                },
                "registrationNumber": "REG-1",
                "numberOfGuests": 1,
                "countryOfGuests": ["ZZZ"],
                "temporal": {
                    "startDatetime": "2025-01-01T00:00:00Z",
                    "endDatetime": "2025-01-02T00:00:00Z",
                },
            }
        )
    with pytest.raises(ValueError, match="must equal the number of elements"):
        ActivityRequest.model_validate(
            {
                "activityId": "activity-1",
                "activityName": None,
                "status": "finished",
                "areaId": "area-1",
                "url": "http://example.com",
                "address": {
                    "thoroughfare": "Street",
                    "locatorDesignatorNumber": 1,
                    "postCode": "1234AB",
                    "postName": "City",
                    "fullAddress": "Street 1, 1234AB City",
                },
                "registrationNumber": "REG-1",
                "numberOfGuests": 2,
                "countryOfGuests": ["NLD"],
                "temporal": {
                    "startDatetime": "2025-01-01T00:00:00Z",
                    "endDatetime": "2025-01-02T00:00:00Z",
                },
            }
        )
    with pytest.raises(ValueError, match="Start datetime year must be >= 2025"):
        validate_year_ge_2025(datetime(2024, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="End datetime must be after start datetime"):
        CommonTemporalRequest.model_validate(
            {
                "startDatetime": "2025-01-02T00:00:00Z",
                "endDatetime": "2025-01-01T00:00:00Z",
            }
        )

    req = ActivityRequest.model_validate(
        {
            "activityId": "",
            "activityName": None,
            "status": "finished",
            "areaId": "area-1",
            "url": "http://example.com",
            "address": {
                "thoroughfare": "Street",
                "locatorDesignatorNumber": 1,
                "postCode": "1234AB",
                "postName": "City",
                "fullAddress": "Street 1, 1234AB City",
            },
            "registrationNumber": "REG-1",
            "numberOfGuests": 1,
            "countryOfGuests": ["NLD"],
            "temporal": {
                "startDatetime": "2025-01-01T00:00:00Z",
                "endDatetime": "2025-01-02T00:00:00Z",
            },
        }
    )
    assert req.activity_id is None
    with pytest.raises(
        RuntimeError, match="activity_id should be set after normalization"
    ):
        _ = req.validated_activity_id

    with pytest.raises(ValueError, match="must be uppercase"):
        ActivityRequest.model_validate(
            {
                "activityId": "activity-1",
                "activityName": None,
                "status": "finished",
                "areaId": "area-1",
                "url": "http://example.com",
                "address": {
                    "thoroughfare": "Street",
                    "locatorDesignatorNumber": 1,
                    "postCode": "1234AB",
                    "postName": "City",
                    "fullAddress": "Street 1, 1234AB City",
                },
                "registrationNumber": "REG-1",
                "numberOfGuests": 1,
                "countryOfGuests": ["nld"],
                "temporal": {
                    "startDatetime": "2025-01-01T00:00:00Z",
                    "endDatetime": "2025-01-02T00:00:00Z",
                },
            }
        )

    activity_response = ActivityResponse.model_validate(
        {
            "activity_id": "activity-1",
            "activity_name": None,
            "status": ActivityStatus.finished,
            "area_id_functional": "area-1",
            "area_name": "Area",
            "competent_authority_id_functional": "ca-1",
            "competent_authority_name": "Authority",
            "url": "http://example.com",
            "address": {
                "thoroughfare": "Street",
                "locator_designator_number": 1,
                "locator_designator_letter": None,
                "locator_designator_addition": None,
                "post_code": "1234AB",
                "post_name": "City",
                "full_address": "Street 1, 1234AB City",
            },
            "registration_number": "REG-1",
            "number_of_guests": 1,
            "country_of_guests": ["NLD"],
            "temporal": {
                "start_date_time": "2025-01-01T00:00:00Z",
                "end_date_time": "2025-01-02T00:00:00Z",
            },
            "platform_id_functional": "platform-1",
            "platform_name": "Platform",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        }
    )
    dumped = activity_response.model_dump(by_alias=True, mode="json")
    assert "activityName" not in dumped
    assert dumped["areaName"] == "Area"
    assert "competentAuthorityName" in dumped
    assert dumped["registrationNumber"] == "REG-1"

    activity_response_without_ca_name = ActivityResponse.model_validate(
        {
            "activity_id": "activity-2",
            "activity_name": "Shown",
            "status": ActivityStatus.finished,
            "area_id_functional": "area-1",
            "area_name": None,
            "competent_authority_id_functional": "ca-1",
            "competent_authority_name": None,
            "url": "http://example.com",
            "address": {
                "thoroughfare": "Street",
                "locator_designator_number": 1,
                "locator_designator_letter": None,
                "locator_designator_addition": None,
                "post_code": "1234AB",
                "post_name": "City",
                "full_address": "Street 1, 1234AB City",
            },
            "registration_number": "REG-2",
            "number_of_guests": 1,
            "country_of_guests": ["NLD"],
            "temporal": {
                "start_date_time": "2025-01-01T00:00:00Z",
                "end_date_time": "2025-01-02T00:00:00Z",
            },
            "platform_id_functional": "platform-1",
            "platform_name": "Platform",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        }
    )
    dumped_without_ca_name = activity_response_without_ca_name.model_dump(
        by_alias=True, mode="json"
    )
    assert dumped_without_ca_name["activityName"] == "Shown"
    assert "areaName" not in dumped_without_ca_name
    assert "competentAuthorityName" not in dumped_without_ca_name

    area_response = AreaResponse.model_validate(
        {
            "area_id": "area-1",
            "area_name": None,
            "regulation": Regulation.all,
            "filename": "area.zip",
            "competent_authority": {
                "competent_authority_id": "ca-1",
                "competent_authority_name": "Authority",
            },
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        }
    )
    assert "areaName" not in area_response.model_dump(by_alias=True, mode="json")
