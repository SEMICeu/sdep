"""Common Temporal composite schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import UtcDateTime  # noqa: TC001

__all__ = [
    "CommonTemporalRequest",
    "CommonTemporalRequestV2",
    "CommonTemporalResponse",
]


def as_utc(v: datetime) -> datetime:
    """Naive input counts as UTC (v1 accepts naive and date-only values).

    Matches how PostgreSQL stores a naive value in a timestamptz column, and keeps
    every stored datetime aware so later comparisons never mix naive and aware.
    """
    return v if v.tzinfo is not None else v.replace(tzinfo=UTC)


def validate_year_ge_2025(v: datetime) -> datetime:
    """Validate that datetime year is >= 2025."""
    if v.year < 2025:
        raise ValueError("Start datetime year must be >= 2025")
    return v


class CommonTemporalRequest(BaseModel):
    """Temporal composite schema for activity requests.

    Validation Layer:
    - Validates datetime formats
    - Date-only and naive submissions are permitted, and are stored as UTC (date-only as 00:00:00Z)
    - Ensures start year is >= 2025
    - Ensures start is before end
    """

    model_config = ConfigDict(
        title="Common.TemporalRequest",
        populate_by_name=True,
    )

    start_date_time: Annotated[
        datetime, AfterValidator(as_utc), AfterValidator(validate_year_ge_2025)
    ] = Field(
        ...,
        alias="startDatetime",
        description="Start date and time of the rental activity (year must be >= 2025)",
        examples=["2025-06-01T14:00:00Z"],
    )  # Attribute

    end_date_time: Annotated[datetime, AfterValidator(as_utc)] = Field(
        ...,
        alias="endDatetime",
        description="End date and time of the rental activity (must be after startDatetime)",
        examples=["2025-06-07T11:00:00Z"],
    )  # Attribute

    @field_validator("end_date_time")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        """Validate end datetime is after start datetime."""
        start = info.data.get("start_date_time")
        if start is not None and v <= start:
            raise ValueError("End datetime must be after start datetime")
        return v


class CommonTemporalRequestV2(CommonTemporalRequest):
    """Temporal composite schema for STR v2 activity requests.

    Tightens v1: both timestamps must carry the UTC offset `Z` or
    `+00:00`. Naive and date-only values are rejected. The start-before-end and
    year >= 2025 rules are inherited.
    """

    model_config = ConfigDict(
        title="Common.TemporalRequestV2",
        populate_by_name=True,
    )

    start_date_time: Annotated[UtcDateTime, AfterValidator(validate_year_ge_2025)] = (
        Field(
            ...,
            alias="startDatetime",
            description="Start date and time of the rental activity, in UTC with offset `Z` or `+00:00` (year must be >= 2025)",
            examples=["2025-06-01T14:00:00Z"],
        )
    )  # Attribute

    end_date_time: UtcDateTime = Field(
        ...,
        alias="endDatetime",
        description="End date and time of the rental activity, in UTC with offset `Z` or `+00:00` (must be after startDatetime)",
        examples=["2025-06-07T11:00:00Z"],
    )  # Attribute


class CommonTemporalResponse(BaseModel):
    """Temporal composite schema for activity responses."""

    model_config = ConfigDict(
        title="Common.TemporalResponse",
        from_attributes=True,
        populate_by_name=True,
    )

    start_datetime: datetime = Field(
        ...,
        serialization_alias="startDatetime",
        validation_alias="start_date_time",
        description="Start date and time of the rental activity",
    )  # Attribute
    end_datetime: datetime = Field(
        ...,
        serialization_alias="endDatetime",
        validation_alias="end_date_time",
        description="End date and time of the rental activity",
    )  # Attribute
