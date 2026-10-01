"""Bulk listing screening service (`POST /listing-screenings/bulk`, LSA).

1. Pydantic Check - validate each item individually, mark failures as NOK
2. Referential Integrity Check - the platform and the listing must exist
3. Versioning under lock - the `createdAt` token must be the current version and
   the listing must not be `acknowledged` (`conflict_error` otherwise); the new
   version is `clear` or `flagged`, by the flags
4. Feedback - per-item OK/NOK response preserving original order

Transaction management: see app/services/activity_bulk.py.
"""

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.platform import Platform

from app.crud import listing as listing_crud
from app.crud import platform as platform_crud
from app.enums import ListingStatus
from app.schemas.listing import ListingScreeningRequest
from app.schemas.listing_bulk import (
    ListingScreeningBulkResponse,
    ListingScreeningBulkResultItem,
)
from app.services.listing_bulk_common import (
    finish,
    last_wins,
    nok_item,
    not_current_message,
    ok_item,
    same_instant,
    validate_items,
)

_item_adapter: TypeAdapter[ListingScreeningRequest] = TypeAdapter(
    ListingScreeningRequest
)


async def screen_listings_bulk(
    session: AsyncSession,
    screenings_raw: list[dict[str, Any]],
) -> ListingScreeningBulkResponse:
    """
    Submit screening results in bulk.

    Args:
        session: Async database session
        screenings_raw: List of raw screening dicts from the request

    Returns:
        ListingScreeningBulkResponse with per-item OK/NOK results
    """
    total = len(screenings_raw)

    # ── Step 1: Pydantic validation (per item) ──────────────────────────
    results, valid_indexes, validated_items, client_supplied_ids = validate_items(
        screenings_raw, _item_adapter, ListingScreeningBulkResultItem
    )

    # ── Intra-batch duplicate handling (last-wins) ──────────────────────
    valid_indexes = last_wins(
        valid_indexes,
        lambda i: (validated_items[i].platform_id, validated_items[i].listing_id),
        results,
        client_supplied_ids,
        ListingScreeningBulkResultItem,
    )

    # ── Step 2: Referential Integrity check (platforms, single query) ───
    unique_platform_ids = list({validated_items[i].platform_id for i in valid_indexes})
    platforms = await platform_crud.get_current_by_platform_ids(
        session, unique_platform_ids
    )

    indexes_by_platform: dict[str, list[int]] = defaultdict(list)
    for i in valid_indexes:
        platform_id = validated_items[i].platform_id
        if platform_id not in platforms:
            results[i] = nok_item(
                ListingScreeningBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=f"Platform with platformId '{platform_id}' not found",
                error_type="not_found_error",
                loc=["platformId"],
            )
        else:
            indexes_by_platform[platform_id].append(i)

    # ── Step 3: Versioning under lock (per platform), then bulk insert ──
    accepted: list[tuple[int, Listing, list[str], Platform]] = []
    for platform_id, indexes in indexes_by_platform.items():
        platform = platforms[platform_id]
        current_by_id = await listing_crud.get_current_by_listing_ids(
            session,
            [validated_items[i].listing_id for i in indexes],
            platform.platform_id,
            for_update=True,
        )
        ids_to_end: list[str] = []
        for i in indexes:
            screening = validated_items[i]
            current = current_by_id.get(screening.listing_id)
            if current is None:
                results[i] = nok_item(
                    ListingScreeningBulkResultItem,
                    i,
                    client_supplied_ids[i],
                    msg=f"Listing '{screening.listing_id}' not found for platform '{platform_id}'",
                    error_type="not_found_error",
                    loc=["listingId"],
                )
            elif not same_instant(current.created_at, screening.created_at):
                results[i] = nok_item(
                    ListingScreeningBulkResultItem,
                    i,
                    client_supplied_ids[i],
                    msg=not_current_message(screening.listing_id, screening.created_at),
                    error_type="conflict_error",
                    loc=["createdAt"],
                )
            elif current.status == ListingStatus.acknowledged:
                results[i] = nok_item(
                    ListingScreeningBulkResultItem,
                    i,
                    client_supplied_ids[i],
                    msg=f"Listing '{screening.listing_id}' is already acknowledged",
                    error_type="conflict_error",
                    loc=["listingId"],
                )
            else:
                ids_to_end.append(screening.listing_id)
                flags = [flag.value for flag in screening.flags]
                accepted.append((i, current, flags, platform))
        await listing_crud.bulk_mark_as_ended(session, ids_to_end, platform.platform_id)

    # Build after the last UPDATE: a version built earlier sits in the
    # relationship collections during autoflush without being in the session.
    batch_created_at = datetime.now(UTC)
    new_versions = [
        listing_crud.build_next_version(
            current,
            platform=platform,
            created_at=batch_created_at,
            status=ListingStatus.flagged if flags else ListingStatus.clear,
            flags=flags,
            screened_at=batch_created_at,
            acknowledged_at=None,
        )
        for _, current, flags, platform in accepted
    ]
    created = await listing_crud.bulk_create(session, new_versions)

    # ── Step 4: Feedback ────────────────────────────────────────────────
    for (i, _, _, _), listing in zip(accepted, created, strict=True):
        results[i] = ok_item(
            ListingScreeningBulkResultItem, i, client_supplied_ids[i], listing
        )

    return finish(ListingScreeningBulkResponse, total, results)
