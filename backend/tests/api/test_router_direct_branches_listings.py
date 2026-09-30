"""Direct calls into the listing handlers and STR bulk routers.

HTTP-driven tests do not yield line coverage for the awaited endpoint bodies in
this suite (see test_router_direct_branches.py). Behaviour is proven in
tests/api/test_listings.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest
from app.api.common import listing_handlers
from app.api.common.auth_dependencies import Client, NamedClient
from app.api.domains.str.routers import (
    listing_acknowledgements_bulk_v2,
    listings_bulk_v2,
)
from app.enums import ListingStatus
from app.schemas.listing import ListingRequest, ListingResponse, ListingScope
from app.schemas.listing_bulk import (
    ListingAcknowledgementBulkRequest,
    ListingAcknowledgementBulkResponse,
    ListingBulkRequest,
    ListingBulkResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _listing_row():
    return SimpleNamespace(
        listing_id="l-1",
        listing_name=None,
        status=ListingStatus.pending,
        flags=[],
        area_id_functional="area-1",
        area_name=None,
        competent_authority_id_functional="ca-1",
        competent_authority_name=None,
        url="http://example.com/l-1",
        address=SimpleNamespace(
            thoroughfare="Turfmarkt",
            locator_designator_number=147,
            locator_designator_letter=None,
            locator_designator_addition=None,
            post_code="2500EA",
            post_name="Den Haag",
            full_address="Turfmarkt 147, 2500EA Den Haag",
        ),
        declared_as_short_term_rental=True,
        registration_number=None,
        submitted_at=datetime(2026, 9, 7, 8, 0),
        screened_at=None,
        acknowledged_at=None,
        platform_id_functional="p-1",
        platform_name="STR",
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_listing_handlers_direct(monkeypatch):
    monkeypatch.setattr(
        listing_handlers.listing,
        "get_listing_list",
        AsyncMock(return_value=[_listing_row()]),
    )
    monkeypatch.setattr(
        listing_handlers.listing, "count_current_listings", AsyncMock(return_value=1)
    )
    session = cast("AsyncSession", object())
    listed = await listing_handlers.list_listings(scope=ListingScope(), session=session)
    dumped = listed.listings[0].model_dump(by_alias=True)
    assert dumped["listingId"] == "l-1"
    # Optional names are dropped when None; timestamps are UTC-aware
    assert "areaName" not in dumped and "competentAuthorityName" not in dumped
    assert "listingName" not in dumped
    assert dumped["submittedAt"].tzinfo is UTC
    counted = await listing_handlers.count_listings(
        scope=ListingScope(), session=session
    )
    assert counted.count == 1


@pytest.mark.asyncio
async def test_str_listing_bulk_routers_direct(monkeypatch):
    submit = AsyncMock(
        return_value=ListingBulkResponse(
            totalReceived=1, succeeded=0, failed=1, results=[]
        )
    )
    monkeypatch.setattr(
        listings_bulk_v2.listing_bulk_service, "create_listings_bulk", submit
    )
    response = await listings_bulk_v2.post_listings_bulk(
        ListingBulkRequest.model_construct(listings=[{"any": "value"}]),
        client=NamedClient(id="str-1", name="STR"),
        session=cast("AsyncSession", object()),
    )
    assert response.status_code == 422
    assert submit.await_args is not None
    assert submit.await_args.kwargs["platform_name"] == "STR"

    acknowledge = AsyncMock(
        return_value=ListingAcknowledgementBulkResponse(
            totalReceived=2, succeeded=1, failed=1, results=[]
        )
    )
    monkeypatch.setattr(
        listing_acknowledgements_bulk_v2.acknowledgement_service,
        "acknowledge_listings_bulk",
        acknowledge,
    )
    response = (
        await listing_acknowledgements_bulk_v2.post_listing_acknowledgements_bulk(
            ListingAcknowledgementBulkRequest.model_construct(acknowledgements=[{}]),
            client=Client(id="str-1"),
            session=cast("AsyncSession", object()),
        )
    )
    assert response.status_code == 200
    assert acknowledge.await_args is not None
    assert acknowledge.await_args.kwargs["client_id"] == "str-1"


def test_listing_schema_guards():
    request = ListingRequest.model_validate(
        {
            "areaId": "area-1",
            "url": "http://example.com/x",
            "address": {
                "thoroughfare": "Turfmarkt",
                "postCode": "2500EA",
                "postName": "Den Haag",
                "fullAddress": "Turfmarkt, 2500EA Den Haag",
            },
            "declaredAsShortTermRental": False,
        }
    )
    with pytest.raises(RuntimeError, match="should be set after normalization"):
        _ = request.validated_listing_id
    request.listing_id = "l-1"
    assert request.validated_listing_id == "l-1"
    assert ListingResponse.model_validate(_listing_row()).area_name is None
