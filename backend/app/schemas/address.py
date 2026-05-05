"""Common Address composite schemas (INSPIRE/STR-AP field names)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "CommonAddressRequest",
    "CommonAddressResponse",
]


class CommonAddressRequest(BaseModel):
    """Address composite schema for activity requests (INSPIRE/STR-AP field names).

    Validation Layer:
    - All syntax validation (lengths, types, constraints) happens here
    - Service layer receives validated data
    """

    model_config = ConfigDict(
        title="Common.AddressRequest",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    thoroughfare: str = Field(
        ...,
        max_length=80,
        description="Street / public space name",
        examples=["Prinsengracht"],
    )  # Attribute

    locator_designator_number: int | None = Field(
        None,
        alias="locatorDesignatorNumber",
        ge=0,
        description="Numeric house number component (optional, >= 0 when provided)",
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

    full_address: str = Field(
        ...,
        alias="fullAddress",
        max_length=318,
        description="Full address as a single string (required, max 318 chars)",
        examples=["Turfmarkt 147a-5h, 2500EA Den Haag"],
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


class CommonAddressResponse(BaseModel):
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
