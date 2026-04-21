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
    TypeAdapter,
    ValidationError,
    model_serializer,
    model_validator,
)
from pydantic_extra_types.country import CountryAlpha3

from app.enums import ActivityStatus
from app.schemas.address import (  # noqa: TC001
    CommonAddressRequest,
    CommonAddressResponse,
)
from app.schemas.common import FunctionalId, OptionalFunctionalId  # noqa: TC001
from app.schemas.temporal import (  # noqa: TC001
    CommonTemporalRequest,
    CommonTemporalResponse,
)

_country_alpha3_adapter = TypeAdapter(CountryAlpha3)


def _validate_country_code_or_na(v: str) -> str:
    """Accept either ``"N/A"`` or a valid ISO 3166-1 alpha-3 country code.

    Uppercase-only (rejects lowercase forms like ``"nld"`` or ``"n/a"``).
    """
    if not isinstance(v, str) or v != v.upper():
        raise ValueError(
            f"Country code '{v}' must be uppercase (ISO 3166-1 alpha-3 or 'N/A')"
        )
    if v == "N/A":
        return v
    try:
        _country_alpha3_adapter.validate_python(v)
    except ValidationError as exc:
        raise ValueError(
            f"Country code '{v}' is not a valid ISO 3166-1 alpha-3 code or 'N/A'"
        ) from exc
    return v


CountryAlpha3OrNA = Annotated[str, AfterValidator(_validate_country_code_or_na)]

__all__ = [
    "ActivityCountResponse",
    "ActivityListResponse",
    "ActivityRequest",
    "ActivityResponse",
]


def empty_string_to_none(v: str | None) -> str | None:
    """Convert empty string to None for optional ID fields.

    This allows clients to send "" instead of omitting the field,
    and the ID will be auto-generated as UUID downstream.
    """
    if v == "":
        return None
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
        title="Activity.Request",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    activity_id: Annotated[
        OptionalFunctionalId,
        BeforeValidator(empty_string_to_none),
    ] = Field(
        None,
        alias="activityId",
        description="Functional ID identifying this activity (auto-generated UUID if not provided; alphanumeric with hyphens `^[A-Za-z0-9-]+$`, max 64 chars)",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID

    activity_name: str | None = Field(
        None,
        alias="activityName",
        max_length=64,
        description="Display name (optional, max 64 chars) of the activity",
        examples=["Amsterdam Summer Rental"],
    )  # Functional name

    status: ActivityStatus = Field(
        ActivityStatus.finished,
        description="Lifecycle status of the activity. Defaults to `finished` when omitted; may also be `cancelled`.",
        examples=["finished", "cancelled"],
    )

    area_id: FunctionalId = Field(
        ...,
        alias="areaId",
        description="Functional ID referencing the area where the activity took place",
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

    address: CommonAddressRequest = Field(
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

    number_of_guests: int = Field(
        ...,
        alias="numberOfGuests",
        ge=1,
        le=1024,
        description="Number of guests (1-1024)",
        examples=[4],
    )  # Attribute

    # Elements validated against ISO 3166-1 alpha-3 country codes, plus the
    # sentinel "N/A" for unknown/unreported nationalities. Uppercase only.
    country_of_guests: list[CountryAlpha3OrNA] = Field(
        ...,
        alias="countryOfGuests",
        min_length=1,
        max_length=1024,
        description="Array of country codes of guests (1-1024; each element is ISO 3166-1 alpha-3 or 'N/A', uppercase only). Length must equal numberOfGuests.",
        examples=[["NLD", "NLD", "DEU", "BEL"]],
    )  # Attribute

    @model_validator(mode="after")
    def validate_guest_cardinality(self) -> ActivityRequest:
        """Enforce DATAMODEL class constraint: numberOfGuests == len(countryOfGuests)."""
        if len(self.country_of_guests) != self.number_of_guests:
            raise ValueError(
                f"numberOfGuests ({self.number_of_guests}) must equal the number of "
                f"elements in countryOfGuests ({len(self.country_of_guests)})"
            )
        return self

    temporal: CommonTemporalRequest = Field(
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
            "status": self.status,
            "url": self.url,
            "registration_number": self.registration_number,
            "address_thoroughfare": self.address.thoroughfare,
            "address_locator_designator_number": self.address.locator_designator_number,
            "address_locator_designator_letter": self.address.locator_designator_letter,
            "address_locator_designator_addition": self.address.locator_designator_addition,
            "address_post_code": self.address.post_code,
            "address_post_name": self.address.post_name,
            "address_full_address": self.address.full_address,
            "temporal_start_date_time": self.temporal.start_date_time,
            "temporal_end_date_time": self.temporal.end_date_time,
            "area_id": self.area_id,
            "country_of_guests": self.country_of_guests,
            "number_of_guests": self.number_of_guests,
        }


class ActivityResponse(BaseModel):
    """Activity response schema."""

    model_config = ConfigDict(
        title="Activity.Response",
        from_attributes=True,
        populate_by_name=True,
    )

    activity_id: FunctionalId = Field(
        ...,
        alias="activityId",
        description="Functional ID identifying this activity",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID
    activity_name: str | None = Field(
        None,
        alias="activityName",
        max_length=64,
        description="Display name (optional, max 64 chars) of the activity",
    )  # Functional name
    status: ActivityStatus = Field(
        ...,
        description="Lifecycle status of the activity record: `finished` or `cancelled`.",
        examples=["finished", "cancelled"],
    )
    area_id: FunctionalId = Field(
        ...,
        alias="areaId",
        description="Functional ID referencing the area where this activity took place",
        examples=[
            "3ab7c2b9-5c8d-4100-bc3e-00ac115f0495",
            "3AB7C2B9-5C8D-4100-BC3E-00AC115F0495",
        ],
    )  # Functional ID reference
    competent_authority_id: FunctionalId = Field(
        ...,
        alias="competentAuthorityId",
        description="Functional ID referencing the competent authority that owns the area",
        examples=["sdep-ca0363", "SDEP-CA0363"],
    )  # Attribute
    competent_authority_name: str | None = Field(
        None,
        alias="competentAuthorityName",
        max_length=64,
        description="Display name (optional, max 64 chars) of the competent authority",
    )  # Attribute
    url: str = Field(
        ..., description="URL of the originating listing/advertisement"
    )  # Attribute
    address: CommonAddressResponse = Field(
        ..., description="Address composite"
    )  # Composite
    registration_number: str = Field(
        ...,
        alias="registrationNumber",
        description="Registration number for the address",
    )  # Attribute
    number_of_guests: int = Field(
        ..., alias="numberOfGuests", description="Number of guests (1-1024)"
    )  # Attribute
    country_of_guests: list[CountryAlpha3OrNA] = Field(
        ...,
        alias="countryOfGuests",
        description="Array of country codes of guests (each element is ISO 3166-1 alpha-3 or 'N/A'). Length equals numberOfGuests.",
    )  # Attribute
    temporal: CommonTemporalResponse = Field(
        ..., description="Temporal composite"
    )  # Composite
    platform_id: FunctionalId = Field(
        ...,
        alias="platformId",
        description="Functional ID referencing the platform that owns the activity",
        examples=["str01", "STR01"],
    )  # Attribute
    platform_name: str | None = Field(
        None,
        alias="platformName",
        max_length=64,
        description="Display name (optional, max 64 chars) of the platform",
    )  # Attribute
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Timestamp when this activity version was created (UTC)",
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

    model_config = ConfigDict(title="Activity.ListResponse")

    activities: list[ActivityResponse] = Field(..., description="List of activities")


class ActivityCountResponse(BaseModel):
    """Count of activities response schema."""

    model_config = ConfigDict(title="Activity.CountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of activity records",
        examples=[42],
    )  # Attribute
