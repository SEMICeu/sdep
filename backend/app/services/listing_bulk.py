"""Bulk listing submission service (`POST /listings/bulk`, STR).

Application-First Validation flow, as for activities:

1. Pydantic Check - validate each item individually, mark failures as NOK
2. Referential Integrity Check - one SELECT for area IDs; an area must be
   regulated for listings (`regulation_error` otherwise)
3. Versioning under lock - a resubmitted `listingId` is a correction, allowed
   while the current version is `pending` (`conflict_error` otherwise)
4. Feedback - per-item OK/NOK response preserving original order

Transaction management: see app/services/activity_bulk.py.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.listing import Listing

from app.crud import area as area_crud
from app.crud import listing as listing_crud
from app.enums import ListingStatus, Regulation
from app.schemas.listing import ListingBulkCreate, ListingRequest
from app.schemas.listing_bulk import ListingBulkResponse, ListingBulkResultItem
from app.services.listing_bulk_common import (
    finish,
    last_wins,
    nok_item,
    ok_item,
    validate_items,
)
from app.services.platform import ensure_platform

_item_adapter: TypeAdapter[ListingRequest] = TypeAdapter(ListingRequest)


async def create_listings_bulk(
    session: AsyncSession,
    listings_raw: list[dict[str, Any]],
    client_id: str,
    platform_name: str,
) -> ListingBulkResponse:
    """
    Submit listings in bulk for the authenticated platform.

    Args:
        session: Async database session
        listings_raw: List of raw listing dicts from the request
        client_id: Private platform client ID from JWT token
        platform_name: Platform name from JWT token (client_name claim)

    Returns:
        ListingBulkResponse with per-item OK/NOK results
    """
    total = len(listings_raw)

    # ── Step 1: Pydantic validation (per item) ──────────────────────────
    results, valid_indexes, validated_items, client_supplied_ids = validate_items(
        listings_raw, _item_adapter, ListingBulkResultItem
    )
    for i in valid_indexes:
        if validated_items[i].listing_id is None:
            validated_items[i].listing_id = str(uuid.uuid4())

    # ── Platform resolution (once per batch) ────────────────────────────
    platform = await ensure_platform(session, client_id, platform_name)

    # ── Intra-batch duplicate handling (last-wins) ──────────────────────
    valid_indexes = last_wins(
        valid_indexes,
        lambda i: validated_items[i].validated_listing_id,
        results,
        client_supplied_ids,
        ListingBulkResultItem,
    )

    # ── Step 2: Referential Integrity check (single query) ──────────────
    # The lookup stays unfiltered on regulation, so an activity-only area gets
    # its own message instead of "not found".
    unique_area_ids = list({validated_items[i].area_id for i in valid_indexes})
    area_ca_map = await area_crud.get_area_ca_map(session, unique_area_ids)

    still_valid: list[int] = []
    for i in valid_indexes:
        area_id_str = validated_items[i].area_id
        if area_id_str not in area_ca_map:
            results[i] = nok_item(
                ListingBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=f"Area with areaId '{area_id_str}' not found",
                error_type="not_found_error",
                loc=["areaId"],
            )
        elif not area_ca_map[area_id_str].regulation.covers(Regulation.listing):
            results[i] = nok_item(
                ListingBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=f"Area with areaId '{area_id_str}' is regulated for activity only",
                error_type="regulation_error",
                loc=["areaId"],
            )
        else:
            still_valid.append(i)
    valid_indexes = still_valid

    # ── Step 3: Versioning under lock, then bulk insert ─────────────────
    # A correction is only allowed while the platform still owns the state.
    listing_ids = [validated_items[i].validated_listing_id for i in valid_indexes]
    current_by_id = await listing_crud.get_current_by_listing_ids(
        session, listing_ids, platform.platform_id, for_update=True
    )

    still_valid = []
    for i in valid_indexes:
        listing_id = validated_items[i].validated_listing_id
        current = current_by_id.get(listing_id)
        if current is not None and current.status != ListingStatus.pending:
            results[i] = nok_item(
                ListingBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=f"Listing '{listing_id}' is already screened (status '{current.status.value}')",
                error_type="conflict_error",
                loc=["listingId"],
            )
        else:
            still_valid.append(i)
    valid_indexes = still_valid

    ids_to_end = [
        validated_items[i].validated_listing_id
        for i in valid_indexes
        if validated_items[i].validated_listing_id in current_by_id
    ]
    await listing_crud.bulk_mark_as_ended(session, ids_to_end, platform.platform_id)

    # One timestamp for the whole batch: the version token and the submission time
    batch_created_at = datetime.now(UTC)
    new_versions: list[Listing] = []
    for i in valid_indexes:
        listing_req = validated_items[i]
        area = area_ca_map[listing_req.area_id]
        row = ListingBulkCreate(
            **listing_req.model_dump(),
            platform_technical_id=platform.id,
            area_technical_id=area.id,
            created_at=batch_created_at,
            submitted_at=batch_created_at,
        )
        new_versions.append(listing_crud.build_from_request(row, platform, area))
    created = await listing_crud.bulk_create(session, new_versions)

    # ── Step 4: Feedback ────────────────────────────────────────────────
    for i, listing in zip(valid_indexes, created, strict=True):
        results[i] = ok_item(ListingBulkResultItem, i, client_supplied_ids[i], listing)

    return finish(ListingBulkResponse, total, results)
