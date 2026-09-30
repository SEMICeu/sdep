"""Pydantic schemas for the three listing bulk writes.

`POST /listings/bulk`, `POST /listing-screenings/bulk` and
`POST /listing-acknowledgements/bulk` share one result shape: every OK item
embeds the listing as it now is (`Listing.Response`). The screening and
acknowledgement variants only differ in the request field and the OpenAPI
title, so they subclass the listing variant.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, model_serializer

from app.schemas.error import ErrorResponse
from app.schemas.listing import (
    ListingAcknowledgementRequest,
    ListingRequest,
    ListingResponse,
    ListingScreeningRequest,
)

__all__ = [
    "ListingAcknowledgementBulkRequest",
    "ListingAcknowledgementBulkResponse",
    "ListingAcknowledgementBulkResultItem",
    "ListingBulkRequest",
    "ListingBulkResponse",
    "ListingBulkResultItem",
    "ListingScreeningBulkRequest",
    "ListingScreeningBulkResponse",
    "ListingScreeningBulkResultItem",
]

# Items use SkipValidation so one invalid item is NOK without failing the batch;
# the service validates each item. See docs/ARCHITECTURE_TECH.md, Bulk.


class ListingBulkRequest(BaseModel):
    """Bulk listing request schema (`POST /listings/bulk`)."""

    model_config = ConfigDict(title="Listing.BulkRequest")

    listings: list[SkipValidation[ListingRequest]] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Array of listing objects to process (1-1000 items per batch)",
    )


class ListingScreeningBulkRequest(BaseModel):
    """Bulk screening request schema (`POST /listing-screenings/bulk`)."""

    model_config = ConfigDict(title="ListingScreening.BulkRequest")

    screenings: list[SkipValidation[ListingScreeningRequest]] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Array of screening results to process (1-1000 items per batch)",
    )


class ListingAcknowledgementBulkRequest(BaseModel):
    """Bulk acknowledgement request schema (`POST /listing-acknowledgements/bulk`)."""

    model_config = ConfigDict(title="ListingAcknowledgement.BulkRequest")

    acknowledgements: list[SkipValidation[ListingAcknowledgementRequest]] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Array of acknowledgements to process (1-1000 items per batch)",
    )


class ListingBulkResultItem(BaseModel):
    """Result for a single item in a listing bulk response."""

    model_config = ConfigDict(
        title="Listing.BulkResultItem",
        populate_by_name=True,
    )

    listing_index: int = Field(
        ...,
        alias="listingIndex",
        ge=0,
        description="Zero-based index of this item in the original request list",
        examples=[0],
    )

    listing_id: str | None = Field(
        None,
        alias="listingId",
        description="Listing functional ID provided by the client in the request",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )

    status: Literal["OK", "NOK"] = Field(
        ...,
        description="Processing result - `OK` (new listing version created) or `NOK` (failed validation or processing)",
        examples=["OK"],
    )

    listing: ListingResponse | None = Field(
        None,
        description="The listing as it now is (present for OK items, omitted for NOK items)",
    )

    errors: ErrorResponse | None = Field(
        None,
        description="Structured error details (present for NOK items, omitted for OK items)",
        examples=[
            {
                "detail": [
                    {
                        "msg": "Listing 'abc-123' version '2026-09-07T08:00:00Z' is no longer current",
                        "type": "conflict_error",
                        "loc": ["createdAt"],
                    }
                ]
            }
        ],
    )

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude errors and listing from response when None."""
        data = serializer(self)
        if data.get("errors") is None:
            data.pop("errors", None)
        if data.get("listing") is None:
            data.pop("listing", None)
        return data


class ListingScreeningBulkResultItem(ListingBulkResultItem):
    """Result for a single item in a screening bulk response."""

    model_config = ConfigDict(
        title="ListingScreening.BulkResultItem",
        populate_by_name=True,
    )


class ListingAcknowledgementBulkResultItem(ListingBulkResultItem):
    """Result for a single item in an acknowledgement bulk response."""

    model_config = ConfigDict(
        title="ListingAcknowledgement.BulkResultItem",
        populate_by_name=True,
    )


class ListingBulkResponse(BaseModel):
    """Bulk listing response schema: per-item OK/NOK feedback with summary counts."""

    model_config = ConfigDict(
        title="Listing.BulkResponse",
        populate_by_name=True,
    )

    total_received: int = Field(
        ...,
        alias="totalReceived",
        ge=0,
        description="Total number of items received in the request",
        examples=[2],
    )

    succeeded: int = Field(
        ...,
        ge=0,
        description="Number of items successfully processed (status OK)",
        examples=[2],
    )

    failed: int = Field(
        ...,
        ge=0,
        description="Number of items that failed validation or processing (status NOK)",
        examples=[0],
    )

    results: list[ListingBulkResultItem] = Field(
        ...,
        description="Per-item results preserving the original request order",
    )


class ListingScreeningBulkResponse(ListingBulkResponse):
    """Bulk screening response schema."""

    model_config = ConfigDict(
        title="ListingScreening.BulkResponse",
        populate_by_name=True,
    )

    results: list[ListingScreeningBulkResultItem] = Field(
        ...,
        description="Per-item results preserving the original request order",
    )


class ListingAcknowledgementBulkResponse(ListingBulkResponse):
    """Bulk acknowledgement response schema."""

    model_config = ConfigDict(
        title="ListingAcknowledgement.BulkResponse",
        populate_by_name=True,
    )

    results: list[ListingAcknowledgementBulkResultItem] = Field(
        ...,
        description="Per-item results preserving the original request order",
    )
