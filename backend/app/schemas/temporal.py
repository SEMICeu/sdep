"""Common Temporal composite schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "CommonTemporalRequest",
    "CommonTemporalResponse",
]


def validate_year_ge_2025(v: datetime) -> datetime:
    """Validate that datetime year is >= 2025."""
    if v.year < 2025:
        raise ValueError("Start datetime year must be >= 2025")
    return v


class CommonTemporalRequest(BaseModel):
    """Temporal composite schema for activity requests.

    Validation Layer:
    - Validates datetime formats
    - Date-only submissions are permitted, and will be stored internally using a 00:00:00 timestamp
    - Ensures start year is >= 2025
    - Ensures start is before end
    """

    model_config = ConfigDict(
        title="Common.TemporalRequest",
        populate_by_name=True,
    )

    start_date_time: Annotated[datetime, AfterValidator(validate_year_ge_2025)] = Field(
        ...,
        alias="startDatetime",
        description="Start date and time of the rental activity (year must be >= 2025)",
        examples=["2025-06-01T14:00:00Z"],
    )  # Attribute

    end_date_time: datetime = Field(
        ...,
        alias="endDatetime",
        description="End date and time of the rental activity (must be after startDatetime)",
        examples=["2025-06-07T11:00:00Z"],
    )  # Attribute

    @field_validator("end_date_time")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        """Validate end datetime is after start datetime."""
        if "start_date_time" in info.data and v <= info.data["start_date_time"]:
            raise ValueError("End datetime must be after start datetime")
        return v


class CommonTemporalResponse(BaseModel):
    """Temporal composite schema for activity responses."""

    model_config = ConfigDict(
        title="Common.TemporalResponse",
        populate_by_name=True,
    )

    startDatetime: datetime = Field(
        ...,
        alias="startDatetime",
        description="Start date and time of the rental activity",
    )  # Attribute
    endDatetime: datetime = Field(
        ..., alias="endDatetime", description="End date and time of the rental activity"
    )  # Attribute
