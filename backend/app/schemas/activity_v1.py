"""Frozen activity schemas for the stable v1 APIs (STR v1 bulk, CA v1 responses).

v1 is stable and its contract must not change. The base schemas in
app/schemas/activity.py and app/schemas/address.py carry the v2 field maximums
(`url` 2048, `fullAddress` 328, documented response maximums); this module
redeclares the affected fields with the v1 values, so the v1 OpenAPI stays unchanged.

The class names are kept on purpose: the OpenAPI component key is the class name
(`ActivityRequest`, `ActivityResponse`, `ActivityBulkResponse`), not the module. The
bulk response classes only shape the OpenAPI: the endpoint returns the service
result as JSON, so the response body is the same in v1 and v2. Delete this module together
with v1.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from app.schemas import activity as _base
from app.schemas import activity_bulk as _bulk
from app.schemas import address as _address
from app.schemas.activity import CountryAlpha3OrNA

__all__ = [
    "ActivityBulkRequest",
    "ActivityBulkResponse",
    "ActivityBulkResultItem",
    "ActivityListResponse",
    "ActivityRequest",
    "ActivityResponse",
    "CommonAddressRequest",
    "CommonAddressResponse",
]


class CommonAddressRequest(_address.CommonAddressRequest):
    """Address composite schema for activity requests (INSPIRE/STR-AP field names).

    Validation Layer:
    - All syntax validation (lengths, types, constraints) happens here
    - Service layer receives validated data
    """

    model_config = ConfigDict(
        title="Common.AddressRequest",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    full_address: str = Field(
        ...,
        alias="fullAddress",
        max_length=318,
        description="Full address as a single string (required, max 318 chars)",
        examples=["Turfmarkt 147a-5h, 2500EA Den Haag"],
    )  # Attribute


class ActivityRequest(_base.ActivityRequest):
    """Activity request schema for creating rental activities.

    Activity ID:
    - Optional: If not provided, will be auto-generated (RFC 9562 UUID)

    Activity Name:
    - Optional: Display name (max 64 chars)

    Validation Layer:
    - Validates all syntax constraints (lengths, ranges, types)

    Constraints (enforced at database level):
    - Unique constraint: (activityId, platformId, createdAt) for versioning support
    """

    model_config = ConfigDict(
        title="Activity.Request",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

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


class CommonAddressResponse(_address.CommonAddressResponse):
    """Address composite schema for activity responses (INSPIRE/STR-AP field names)."""

    model_config = ConfigDict(
        title="Common.AddressResponse",
        from_attributes=True,
        populate_by_name=True,
    )

    thoroughfare: str = Field(
        ..., description="Street / public space name"
    )  # Attribute
    locator_designator_number: int | None = Field(
        None,
        serialization_alias="locatorDesignatorNumber",
        description="Numeric house number component (optional)",
    )  # Attribute
    locator_designator_letter: str | None = Field(
        None,
        serialization_alias="locatorDesignatorLetter",
        description="Letter/character suffix (optional)",
    )  # Attribute
    locator_designator_addition: str | None = Field(
        None,
        serialization_alias="locatorDesignatorAddition",
        description="Additional qualifier (optional)",
    )  # Attribute
    post_code: str = Field(
        ..., serialization_alias="postCode", description="Postal code"
    )  # Attribute
    post_name: str = Field(
        ..., serialization_alias="postName", description="City / town / village"
    )  # Attribute
    full_address: str = Field(
        ...,
        serialization_alias="fullAddress",
        description="Full address as a single string",
    )  # Attribute


class ActivityResponse(_base.ActivityResponse):
    """Activity response schema."""

    model_config = ConfigDict(
        title="Activity.Response",
        from_attributes=True,
        populate_by_name=True,
    )

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


class ActivityListResponse(_base.ActivityListResponse):
    """List of activities for GET responses."""

    model_config = ConfigDict(title="Activity.ListResponse")

    activities: list[ActivityResponse] = Field(..., description="List of activities")


class ActivityBulkRequest(BaseModel):
    """Bulk activity request schema.

    The `activities` field is typed as `list[ActivityRequest]` for the OpenAPI
    contract, but item-level validation is skipped at request-parse time (via
    `SkipValidation`). This preserves the Application-First Validation flow:
    each item is validated individually in the service layer, so one invalid
    item is marked NOK without failing the whole batch.
    """

    model_config = ConfigDict(
        title="Activity.BulkRequest",
    )

    activities: list[SkipValidation[ActivityRequest]] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Array of activity objects to process (1-1000 items per batch)",
    )


class ActivityBulkResultItem(_bulk.ActivityBulkResultItem):
    """Result for a single item in a bulk activity response."""

    model_config = ConfigDict(
        title="Activity.BulkResultItem",
        populate_by_name=True,
    )

    activity: ActivityResponse | None = Field(
        None,
        description="The full activity object (present for OK items, omitted for NOK items)",
    )


class ActivityBulkResponse(_bulk.ActivityBulkResponse):
    """Bulk activity response schema.

    Returns per-item OK/NOK feedback with summary counts.
    Validation flow Step 4: the original list enriched with status and error_message.
    """

    model_config = ConfigDict(
        title="Activity.BulkResponse",
        populate_by_name=True,
    )

    results: list[ActivityBulkResultItem] = Field(
        ...,
        description="Per-item results preserving the original request order",
        json_schema_extra=_bulk.ActivityBulkResponse.model_fields[
            "results"
        ].json_schema_extra,
    )
