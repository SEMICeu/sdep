"""Pydantic schemas for Listing API requests and responses.

A listing is one resource with a lifecycle (see docs/LISTING_FUNC.md): the platform
submits it (`Listing.Request`), the listing screening authority screens it
(`ListingScreening.Request`), the platform acknowledges the flags
(`ListingAcknowledgement.Request`). Every audience reads the same
`Listing.Response`.
"""

from __future__ import annotations

from dataclasses import dataclass
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

from app.enums import ListingFlag, ListingStatus
from app.schemas.activity import empty_string_to_none
from app.schemas.address import (
    CommonAddressRequest,
    CommonAddressResponse,
)
from app.schemas.common import (
    FunctionalId,
    OptionalFunctionalId,
    UtcDateTime,
)
from app.schemas.temporal import as_utc

# Response timestamps are always emitted with a UTC offset (`Z`), so `createdAt`
# round-trips as the version token whatever the database dialect returns.
UtcAwareDateTime = Annotated[datetime, AfterValidator(as_utc)]

__all__ = [
    "ListingAcknowledgementRequest",
    "ListingBulkCreate",
    "ListingCountResponse",
    "ListingFilters",
    "ListingListResponse",
    "ListingRequest",
    "ListingResponse",
    "ListingScope",
    "ListingScreeningRequest",
]

ADDRESS_DESCRIPTION = "Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)"


class ListingRequest(BaseModel):
    """Listing request schema, submitted by a platform (`POST /listings/bulk`).

    Listing ID:
    - Optional: If not provided, will be auto-generated (RFC 9562 UUID)
    - Resubmitting the same ID corrects the listing while it is `pending`

    Constraints (enforced at database level):
    - Unique constraint: (listingId, platformId, createdAt) for versioning support
    """

    model_config = ConfigDict(
        title="Listing.Request",
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    listing_id: Annotated[
        OptionalFunctionalId,
        BeforeValidator(empty_string_to_none),
    ] = Field(
        None,
        alias="listingId",
        description="Functional ID identifying the listing (alphanumeric with hyphens `^[A-Za-z0-9\\-]+$`, max 64 chars, optionally supplied, auto-generated as UUIDv4 RFC 9562 if not supplied). Resubmitting an ID corrects the listing while it is `pending`.",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
        ],
    )  # Functional ID

    listing_name: str | None = Field(
        None,
        alias="listingName",
        max_length=64,
        description="Display name of the listing (optional, max 64 chars)",
        examples=["Amsterdam Canal Apartment"],
    )  # Functional name

    area_id: FunctionalId = Field(
        ...,
        alias="areaId",
        description="Functional ID referencing the area where the listing is posted",
        examples=[
            "58ff0814-3aa1-5019-9afb-3cd9f398602c",
            "974e2c23-b666-5044-a05c-9479a4c293a1",
        ],
    )  # Functional ID reference

    # 2048 is a chosen pragmatic cap, not a browser limit. See docs/DATAMODEL_TECH.md, Activity.
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL referencing the listing online (max 2048 chars)",
        examples=["http://example.com/amsterdam-canal-apartment"],
    )  # Attribute

    address: CommonAddressRequest = Field(
        ...,
        description=ADDRESS_DESCRIPTION,
    )  # Composite

    declared_as_short_term_rental: bool = Field(
        ...,
        alias="declaredAsShortTermRental",
        description="Host self-declaration: `true` when the host declared the listing as a short-term rental",
        examples=[True],
    )  # Attribute

    registration_number: str | None = Field(
        None,
        alias="registrationNumber",
        min_length=1,
        max_length=32,
        description="Registration number shown on the listing (optional, max 32 chars)",
        examples=["REG0001"],
    )  # Attribute

    @property
    def validated_listing_id(self) -> str:
        """Return the normalized listing_id after bulk-service enrichment."""
        if not isinstance(self.listing_id, str):
            raise RuntimeError("listing_id should be set after normalization")
        return self.listing_id


class ListingScreeningRequest(BaseModel):
    """Screening result for one listing, submitted by the listing screening authority."""

    model_config = ConfigDict(
        title="ListingScreening.Request",
        populate_by_name=True,
    )

    platform_id: FunctionalId = Field(
        ...,
        alias="platformId",
        description="Functional ID of the platform that submitted the listing (a `listingId` is only unique within a platform)",
        examples=["8e70f1e2-4c61-477b-89b8-0dbf25ab8b21"],
    )  # Functional ID reference

    listing_id: FunctionalId = Field(
        ...,
        alias="listingId",
        description="Functional ID of the screened listing",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )  # Functional ID reference

    created_at: UtcDateTime = Field(
        ...,
        alias="createdAt",
        description="`createdAt` of the listing version that was screened (UTC); refused with `conflict_error` when that version is no longer current",
        examples=["2026-09-07T08:00:00Z"],
    )  # Concurrency token

    flags: list[ListingFlag] = Field(
        ...,
        max_length=7,
        description="Flag codes raised by the screening; empty means `clear`, non-empty means `flagged`",
        examples=[["UNK"], []],
    )  # Attribute

    @field_validator("flags")
    @classmethod
    def validate_flags_distinct(cls, v: list[ListingFlag]) -> list[ListingFlag]:
        """Reject duplicate flag codes."""
        if len(set(v)) != len(v):
            raise ValueError("Flag codes must be distinct")
        return v


class ListingAcknowledgementRequest(BaseModel):
    """Acknowledgement of a flagged listing, submitted by the platform."""

    model_config = ConfigDict(
        title="ListingAcknowledgement.Request",
        populate_by_name=True,
    )

    listing_id: FunctionalId = Field(
        ...,
        alias="listingId",
        description="Functional ID of the flagged listing (scoped to the authenticated platform)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )  # Functional ID reference

    created_at: UtcDateTime = Field(
        ...,
        alias="createdAt",
        description="`createdAt` of the flagged listing version (UTC); refused with `conflict_error` when that version is no longer current",
        examples=["2026-09-07T08:00:00Z"],
    )  # Concurrency token


class ListingBulkCreate(ListingRequest):
    """Validated listing payload enriched with technical IDs for bulk insert."""

    platform_technical_id: int
    area_technical_id: int
    created_at: datetime
    submitted_at: datetime


@dataclass(frozen=True)
class ListingFilters:
    """Optional query filters for listing reads (AND semantics)."""

    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    platform_id: str | None = None
    area_id: str | None = None
    competent_authority_id: str | None = None
    flags: tuple[ListingFlag, ...] | None = None
    status: ListingStatus | None = None


@dataclass(frozen=True)
class ListingScope:
    """Fixed read scope per audience, decided by the router (never by a filter).

    A platform sees its own listings, a competent authority its own areas, the
    other audiences everything. `status` narrows the audience to one lifecycle
    state (STR: flagged, LSA: pending, CA: acknowledged) or is None for all.
    """

    platform_client_id: str | None = None
    competent_authority_client_id: str | None = None
    status: ListingStatus | None = None


# Field maximums mirror ListingRequest, so clients can size their storage from the
# response contract.
class ListingResponse(BaseModel):
    """Listing response schema, the same for every audience."""

    model_config = ConfigDict(
        title="Listing.Response",
        from_attributes=True,
        populate_by_name=True,
    )

    listing_id: FunctionalId = Field(
        ...,
        serialization_alias="listingId",
        description="Functional ID identifying this listing",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )  # Functional ID
    listing_name: str | None = Field(
        None,
        serialization_alias="listingName",
        max_length=64,
        description="Display name (optional) of the listing",
    )  # Functional name
    status: ListingStatus = Field(
        ...,
        description="Lifecycle status: `pending`, `clear`, `flagged` or `acknowledged`",
        examples=["flagged"],
    )
    flags: list[ListingFlag] = Field(
        ...,
        description="Flag codes raised by the screening (empty until screened; non-empty when `flagged` or `acknowledged`)",
        examples=[["UNK"]],
    )  # Attribute
    area_id: FunctionalId = Field(
        ...,
        serialization_alias="areaId",
        # The ORM model exposes a convenience property for the functional area ID.
        validation_alias="area_id_functional",
        description="Functional ID referencing the area where the listing is posted",
        examples=["58ff0814-3aa1-5019-9afb-3cd9f398602c"],
    )  # Functional ID reference
    area_name: str | None = Field(
        None,
        serialization_alias="areaName",
        max_length=64,
        description="Display name (optional) of the area",
    )  # Attribute
    competent_authority_id: FunctionalId = Field(
        ...,
        serialization_alias="competentAuthorityId",
        # The ORM model exposes a convenience property for the functional CA ID.
        validation_alias="competent_authority_id_functional",
        description="Functional ID referencing the competent authority that owns the area",
        examples=["c4ac8ccf-a281-5789-bad7-28dfac20ca7f"],
    )  # Attribute
    competent_authority_name: str | None = Field(
        None,
        serialization_alias="competentAuthorityName",
        max_length=64,
        description="Display name (optional) of the competent authority",
    )  # Attribute
    url: str = Field(
        ...,
        max_length=2048,
        description="URL referencing the listing online (max 2048 chars)",
    )  # Attribute
    address: CommonAddressResponse = Field(
        ...,
        description=ADDRESS_DESCRIPTION,
    )  # Composite
    declared_as_short_term_rental: bool = Field(
        ...,
        serialization_alias="declaredAsShortTermRental",
        description="Host self-declaration: `true` when the host declared the listing as a short-term rental",
    )  # Attribute
    registration_number: str | None = Field(
        None,
        serialization_alias="registrationNumber",
        max_length=32,
        description="Registration number shown on the listing (optional, max 32 chars)",
    )  # Attribute
    submitted_at: UtcAwareDateTime = Field(
        ...,
        serialization_alias="submittedAt",
        description="Timestamp of the platform's submission (UTC); unchanged by screening and acknowledgement",
    )  # Attribute
    screened_at: UtcAwareDateTime | None = Field(
        None,
        serialization_alias="screenedAt",
        description="Timestamp of the screening (UTC); null until screened",
    )  # Attribute
    acknowledged_at: UtcAwareDateTime | None = Field(
        None,
        serialization_alias="acknowledgedAt",
        description="Timestamp of the acknowledgement (UTC); null until acknowledged",
    )  # Attribute
    platform_id: FunctionalId = Field(
        ...,
        serialization_alias="platformId",
        # The ORM model exposes a convenience property for the functional platform ID.
        validation_alias="platform_id_functional",
        description="Functional ID referencing the platform that submitted the listing",
        examples=["8e70f1e2-4c61-477b-89b8-0dbf25ab8b21"],
    )  # Attribute
    platform_name: str | None = Field(
        None,
        serialization_alias="platformName",
        max_length=64,
        description="Display name (optional) of the platform",
    )  # Attribute
    created_at: UtcAwareDateTime = Field(
        ...,
        serialization_alias="createdAt",
        description="Timestamp when this listing version was created (UTC); the version token for screening and acknowledgement",
    )  # Attribute

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude optional name fields from response when they're None."""
        data = serializer(self)
        if data.get("listingName") is None:
            data.pop("listingName", None)
        if data.get("areaName") is None:
            data.pop("areaName", None)
        if data.get("competentAuthorityName") is None:
            data.pop("competentAuthorityName", None)
        return data


class ListingListResponse(BaseModel):
    """List of listings for GET responses."""

    model_config = ConfigDict(title="Listing.ListResponse")

    listings: list[ListingResponse] = Field(..., description="List of listings")


class ListingCountResponse(BaseModel):
    """Count of listings response schema."""

    model_config = ConfigDict(title="Listing.CountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of listing records",
        examples=[42],
    )  # Attribute
