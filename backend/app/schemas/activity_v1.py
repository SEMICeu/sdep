"""Frozen activity response schemas for CA v1.

CA v1 is stable and its contract must not change. The base response schemas in
app/schemas/activity.py and app/schemas/address.py document field maximums; this
module re-declares the affected fields without them, so the
CA v1 OpenAPI stays byte-identical.

The class names are kept on purpose: the OpenAPI component key is the class name
(`ActivityResponse`), not the module. Delete this module together with CA v1.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.schemas import activity as _base
from app.schemas import address as _address
from app.schemas.activity import CountryAlpha3OrNA  # noqa: TC001

__all__ = [
    "ActivityListResponse",
    "ActivityResponse",
    "CommonAddressResponse",
]


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
