"""Pydantic schemas for Activity API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
)
from pydantic_extra_types.country import CountryAlpha3

from app.schemas.common import FunctionalId, OptionalFunctionalId  # noqa: TC001

__all__ = [
    "ActivityCountResponse",
    "ActivityListResponse",
    "ActivityRequest",
    "ActivityResponse",
    "AddressRequest",
    "AddressResponse",
    "TemporalRequest",
    "TemporalResponse",
]


def validate_year_ge_2025(v: datetime) -> datetime:
    """Validate that datetime year is >= 2025."""
    if v.year < 2025:
        raise ValueError("Start datetime year must be >= 2025")
    return v


def empty_string_to_none(v: str | None) -> str | None:
    """Convert empty string to None for optional ID fields.

    This allows clients to send "" instead of omitting the field,
    and the ID will be auto-generated as UUID downstream.
    """
    if v == "":
        return None
    return v


class AddressRequest(BaseModel):
    """Address composite schema for activity requests (INSPIRE/STR-AP field names).

    Validation Layer:
    - All syntax validation (lengths, types, constraints) happens here
    - Service layer receives validated data
    """

    model_config = ConfigDict(
        title="activity.AddressRequest",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    thoroughfare: str = Field(
        ...,
        max_length=80,
        description="Street / public space name",
        examples=["Prinsengracht"],
    )  # Attribute

    locator_designator_number: int = Field(
        ...,
        alias="locatorDesignatorNumber",
        ge=1,
        description="Numeric house number component",
        examples=[263],
    )  # Attribute

    locator_designator_letter: str | None = Field(
        None,
        alias="locatorDesignatorLetter",
        max_length=10,
        description="Letter/character suffix (optional, e.g. 'a', 'bis', 'ter')",
        examples=["a"],
    )  # Attribute

    locator_designator_addition: str | None = Field(
        None,
        alias="locatorDesignatorAddition",
        max_length=128,
        description="Additional qualifier (optional, e.g. 'II', 'Apt 3')",
        examples=["II"],
    )  # Attribute

    post_code: str = Field(
        ...,
        alias="postCode",
        min_length=1,
        max_length=10,
        pattern=r"^[0-9A-Za-z]+$",
        description="Postal code (no spaces, alphanumeric)",
        examples=["1016GV"],
    )  # Attribute

    post_name: str = Field(
        ...,
        alias="postName",
        max_length=80,
        description="City / town / village",
        examples=["Amsterdam"],
    )  # Attribute

    @field_validator("locator_designator_letter")
    @classmethod
    def validate_locator_designator_letter_is_alphabetic(
        cls, v: str | None
    ) -> str | None:
        """Validate locator designator letter contains only alphabetic characters."""
        if v is not None and not v.isalpha():
            raise ValueError(
                "Locator designator letter must contain only alphabetic characters"
            )
        return v

    @field_validator("post_code")
    @classmethod
    def validate_post_code_format(cls, v: str) -> str:
        """Validate post code has no spaces and is alphanumeric."""
        if " " in v:
            raise ValueError("Post code must not contain spaces")
        if not v.isalnum():
            raise ValueError("Post code must be alphanumeric")
        return v


class TemporalRequest(BaseModel):
    """Temporal composite schema for activity requests.

    Validation Layer:
    - Validates datetime formats
    - Date-only submissions are permitted, and will be stored internally using a 00:00:00 timestamp
    - Ensures start year is >= 2025
    - Ensures start is before end
    """

    model_config = ConfigDict(
        title="activity.TemporalRequest",
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


class ActivityRequest(BaseModel):
    """Activity request schema for creating rental activities.

    Platform:
    - NOT in request payload (extracted from JWT token at API layer)
    - PlatformId comes from token's client_id claim
    - PlatformName comes from token's client_name claim
    - Will be auto-created if it doesn't exist yet

    Activity ID:
    - Optional: If not provided, will be auto-generated (RFC 9562 UUID)

    Activity Name:
    - Optional: Display name (max 64 chars)

    Validation Layer:
    - Validates all syntax constraints (lengths, ranges, types)

    Constraints (enforced at database level):
    - Unique constraint: (activityId, createdAt, platform) for versioning support
    """

    model_config = ConfigDict(
        title="activity.ActivityRequest",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    activity_id: Annotated[
        OptionalFunctionalId,
        BeforeValidator(empty_string_to_none),
    ] = Field(
        None,
        alias="activityId",
        description="Functional ID identifying this activity (optional, auto-generated UUID if not provided; alphanumeric with hyphens `^[A-Za-z0-9-]+$`, max 64 chars)",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID

    activity_name: str | None = Field(
        None,
        alias="activityName",
        max_length=64,
        description="Activity name (optional, human-readable, max 64 chars)",
        examples=["Amsterdam Summer Rental"],
    )  # Functional name

    area_id: FunctionalId = Field(
        ...,
        alias="areaId",
        description="Area functional ID (alphanumeric with hyphens, max 64 chars)",
        examples=[
            "3ab7c2b9-5c8d-4100-bc3e-00ac115f0495",
            "3AB7C2B9-5C8D-4100-BC3E-00AC115F0495",
        ],
    )  # Functional ID reference

    url: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="URL of the originating listing/advertisement (required)",
        examples=["http://example.com/amsterdam-myhouse-1"],
    )  # Attribute

    address: AddressRequest = Field(
        ...,
        description="Address composite (INSPIRE/STR-AP) containing thoroughfare, locatorDesignator sub-fields, postCode, and postName",
    )  # Composite

    registration_number: str = Field(
        ...,
        alias="registrationNumber",
        min_length=1,
        max_length=32,
        description="Registration number for the address",
        examples=["REG0001"],
    )  # Attribute

    number_of_guests: int | None = Field(
        None,
        alias="numberOfGuests",
        ge=1,
        le=1024,
        description="Number of guests (optional, 1-1024 when provided)",
        examples=[4],
    )  # Attribute

    # Uses pydantic-extra-types CountryAlpha3 for ISO 3166-1 alpha-3 validation
    # against actual country codes (not just format). CountryAlpha3 is a str
    # subclass, so no serialization or database impact.
    country_of_guests: list[CountryAlpha3] | None = Field(
        None,
        alias="countryOfGuests",
        max_length=1024,
        description="Array of country codes of guests (optional, validated against ISO 3166-1 alpha-3 country codes, uppercase only, 1-1024 when provided)",
        examples=[["NLD", "NLD", "DEU", "BEL"]],
    )  # Attribute

    @field_validator("country_of_guests", mode="before")
    @classmethod
    def reject_lowercase_country_codes(
        cls,
        v: list[str] | None,
    ) -> list[str] | None:
        """Reject country codes that are not fully uppercase."""
        if v is None:
            return v
        for code in v:
            if isinstance(code, str) and code != code.upper():
                raise ValueError(
                    f"Country code '{code}' must be uppercase (ISO 3166-1 alpha-3)"
                )
        return v

    temporal: TemporalRequest = Field(
        ...,
        description="Temporal composite containing start and end date/time",
    )  # Composite

    def to_service_dict(self, platform_id: str, platform_name: str) -> dict:
        """
        Convert Pydantic model to dictionary for service layer.

        Normalizes metadata (platform) from batch level to each activity.
        Flattens nested composites (address, temporal) to match service layer expectations.
        Converts all field names to snake_case.

        Args:
            platform_id: Platform ID string from JWT token (client_id claim)
            platform_name: Platform name from JWT token (client_name claim)

        Returns:
            Dictionary with snake_case keys and flattened structure
        """
        return {
            "platform_id_str": platform_id,
            "platform_name": platform_name,
            "activity_id": self.activity_id,
            "activity_name": self.activity_name,
            "url": self.url,
            "registration_number": self.registration_number,
            "address_thoroughfare": self.address.thoroughfare,
            "address_locator_designator_number": self.address.locator_designator_number,
            "address_locator_designator_letter": self.address.locator_designator_letter,
            "address_locator_designator_addition": self.address.locator_designator_addition,
            "address_post_code": self.address.post_code,
            "address_post_name": self.address.post_name,
            "temporal_start_date_time": self.temporal.start_date_time,
            "temporal_end_date_time": self.temporal.end_date_time,
            "area_id": self.area_id,
            "country_of_guests": self.country_of_guests,
            "number_of_guests": self.number_of_guests,
        }


class AddressResponse(BaseModel):
    """Address composite schema for activity responses (INSPIRE/STR-AP field names)."""

    model_config = ConfigDict(
        title="activity.AddressResponse",
        populate_by_name=True,
    )

    thoroughfare: str = Field(
        ..., description="Street / public space name"
    )  # Attribute
    locatorDesignatorNumber: int = Field(
        ...,
        alias="locatorDesignatorNumber",
        description="Numeric house number component",
    )  # Attribute
    locatorDesignatorLetter: str | None = Field(
        None,
        alias="locatorDesignatorLetter",
        description="Letter/character suffix (optional)",
    )  # Attribute
    locatorDesignatorAddition: str | None = Field(
        None,
        alias="locatorDesignatorAddition",
        description="Additional qualifier (optional)",
    )  # Attribute
    postCode: str = Field(..., alias="postCode", description="Postal code")  # Attribute
    postName: str = Field(
        ..., alias="postName", description="City / town / village"
    )  # Attribute


class TemporalResponse(BaseModel):
    """Temporal composite schema for activity responses."""

    model_config = ConfigDict(
        title="activity.TemporalResponse",
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


class ActivityResponse(BaseModel):
    """Activity response schema."""

    model_config = ConfigDict(
        title="activity.ActivityResponse",
        from_attributes=True,
        populate_by_name=True,
    )

    activity_id: FunctionalId = Field(
        ...,
        alias="activityId",
        description="Activity functional ID (alphanumeric with hyphens, max 64 chars)",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID
    activity_name: str | None = Field(
        None,
        alias="activityName",
        max_length=64,
        description="Activity name (optional, max 64 chars)",
    )  # Functional name
    area_id: FunctionalId = Field(
        ...,
        alias="areaId",
        description="Area functional ID (alphanumeric with hyphens, max 64 chars)",
        examples=[
            "3ab7c2b9-5c8d-4100-bc3e-00ac115f0495",
            "3AB7C2B9-5C8D-4100-BC3E-00AC115F0495",
        ],
    )  # Functional ID reference
    competent_authority_id: FunctionalId = Field(
        ...,
        alias="competentAuthorityId",
        description="Competent authority functional ID who owns the referenced areaId (alphanumeric with hyphens, max 64 chars)",
        examples=["sdep-ca0363", "SDEP-CA0363"],
    )  # Attribute
    competent_authority_name: str | None = Field(
        None,
        alias="competentAuthorityName",
        max_length=64,
        description="Competent authority name (optional, max 64 chars)",
    )  # Attribute
    url: str = Field(
        ..., description="URL of the originating listing/advertisement"
    )  # Attribute
    address: AddressResponse = Field(..., description="Address composite")  # Composite
    registration_number: str = Field(
        ...,
        alias="registrationNumber",
        description="Registration number for the address",
    )  # Attribute
    number_of_guests: int | None = Field(
        None, alias="numberOfGuests", description="Number of guests (optional)"
    )  # Attribute
    country_of_guests: list[CountryAlpha3] | None = Field(
        None,
        alias="countryOfGuests",
        description="Array of country codes of guests (optional)",
    )  # Attribute
    temporal: TemporalResponse = Field(
        ..., description="Temporal composite"
    )  # Composite
    platform_id: FunctionalId = Field(
        ...,
        alias="platformId",
        description="Functional ID referencing the platform that owns the activity (alphanumeric with hyphens, max 64 chars)",
        examples=["str01", "STR01"],
    )  # Attribute
    platform_name: str | None = Field(
        None,
        alias="platformName",
        max_length=64,
        description="Platform name (optional, max 64 chars)",
    )  # Attribute
    created_at: datetime = Field(
        ..., alias="createdAt", description="Creation timestamp"
    )  # Attribute

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude optional name fields from response when they're None."""
        data = serializer(self)
        if data.get("activityName") is None:
            data.pop("activityName", None)
        if data.get("competentAuthorityName") is None:
            data.pop("competentAuthorityName", None)
        return data


class ActivityListResponse(BaseModel):
    """List of activities for GET responses."""

    model_config = ConfigDict(title="activity.ActivityListResponse")

    activities: list[ActivityResponse] = Field(..., description="List of activities")


class ActivityCountResponse(BaseModel):
    """Count of activities response schema."""

    model_config = ConfigDict(title="activity.ActivityCountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of activity records",
        examples=[42],
    )  # Attribute
