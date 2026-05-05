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
    "ActivityBulkCreate",
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
        description="Functional ID identifying the activity (auto-generated UUID if not provided; alphanumeric with hyphens `^[A-Za-z0-9-]+$`, max 64 chars)",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID

    activity_name: str | None = Field(
        None,
        alias="activityName",
        max_length=64,
        description="Display name of the activity (optional, max 64 chars)",
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
        description="URL of the originating listing/advertisement (max 128 chars)",
        examples=["http://example.com/amsterdam-myhouse-1"],
    )  # Attribute

    address: CommonAddressRequest = Field(
        ...,
        description="Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)",
    )  # Composite

    registration_number: str = Field(
        ...,
        alias="registrationNumber",
        min_length=1,
        max_length=32,
        description="Registration number of the address (max 32 chars)",
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
        description="Temporal composite (`startDatetime`, `endDatetime`)",
    )  # Composite

    @property
    def validated_activity_id(self) -> str:
        """Return the normalized activity_id after bulk-service enrichment."""
        if not isinstance(self.activity_id, str):
            raise RuntimeError("activity_id should be set after normalization")
        return self.activity_id


class ActivityBulkCreate(ActivityRequest):
    """Validated activity payload enriched with technical IDs for bulk insert."""

    platform_technical_id: int
    area_technical_id: int
    created_at: datetime


class ActivityResponse(BaseModel):
    """Activity response schema."""

    model_config = ConfigDict(
        title="Activity.Response",
        from_attributes=True,
        populate_by_name=True,
    )

    activity_id: FunctionalId = Field(
        ...,
        serialization_alias="activityId",
        description="Functional ID identifying this activity",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID
    activity_name: str | None = Field(
        None,
        serialization_alias="activityName",
        max_length=64,
        description="Display name (optional) of the activity",
    )  # Functional name
    status: ActivityStatus = Field(
        ...,
        description="Lifecycle status of the activity: `finished` or `cancelled`.",
        examples=["finished", "cancelled"],
    )
    area_id: FunctionalId = Field(
        ...,
        serialization_alias="areaId",
        # The ORM model exposes a convenience property for the functional area ID.
        validation_alias="area_id_functional",
        description="Functional ID referencing the area where this activity took place",
        examples=[
            "3ab7c2b9-5c8d-4100-bc3e-00ac115f0495",
            "3AB7C2B9-5C8D-4100-BC3E-00AC115F0495",
        ],
    )  # Functional ID reference
    competent_authority_id: FunctionalId = Field(
        ...,
        serialization_alias="competentAuthorityId",
        # The ORM model exposes a convenience property for the functional CA ID.
        validation_alias="competent_authority_id_functional",
        description="Functional ID referencing the competent authority that owns the area",
        examples=["sdep-ca0363", "SDEP-CA0363"],
    )  # Attribute
    competent_authority_name: str | None = Field(
        None,
        serialization_alias="competentAuthorityName",
        max_length=64,
        description="Display name (optional) of the competent authority",
    )  # Attribute
    url: str = Field(
        ..., description="URL of the originating listing/advertisement"
    )  # Attribute
    address: CommonAddressResponse = Field(
        ...,
        description="Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)",
    )  # Composite
    registration_number: str = Field(
        ...,
        serialization_alias="registrationNumber",
        description="Registration number of the address",
    )  # Attribute
    number_of_guests: int = Field(
        ...,
        serialization_alias="numberOfGuests",
        description="Number of guests (1-1024)",
    )  # Attribute
    country_of_guests: list[CountryAlpha3OrNA] = Field(
        ...,
        serialization_alias="countryOfGuests",
        description="Array of country codes of guests (each element is ISO 3166-1 alpha-3 or 'N/A'); array length equals numberOfGuests.",
    )  # Attribute
    temporal: CommonTemporalResponse = Field(
        ..., description="Temporal composite (`startDatetime`, `endDatetime`)"
    )  # Composite
    platform_id: FunctionalId = Field(
        ...,
        serialization_alias="platformId",
        # The ORM model exposes a convenience property for the functional platform ID.
        validation_alias="platform_id_functional",
        description="Functional ID referencing the platform that owns the activity",
        examples=["str01", "STR01"],
    )  # Attribute
    platform_name: str | None = Field(
        None,
        serialization_alias="platformName",
        max_length=64,
        description="Display name (optional) of the platform",
    )  # Attribute
    created_at: datetime = Field(
        ...,
        serialization_alias="createdAt",
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
