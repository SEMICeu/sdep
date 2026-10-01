"""Bulk listing acknowledgement service (`POST /listing-acknowledgements/bulk`, STR).

1. Pydantic Check - validate each item individually, mark failures as NOK
2. Referential Integrity Check - the listing must exist for the platform
3. Versioning under lock - the `createdAt` token must be the current version and
   the listing must be `flagged` (`conflict_error` otherwise); a retried
   acknowledgement fails on the token, which the platform treats as "already
   acknowledged"
4. Feedback - per-item OK/NOK response preserving original order

Transaction management: see app/services/activity_bulk.py.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.listing import Listing

from app.crud import listing as listing_crud
from app.crud import platform as platform_crud
from app.enums import ListingStatus
from app.schemas.listing import ListingAcknowledgementRequest
from app.schemas.listing_bulk import (
    ListingAcknowledgementBulkResponse,
    ListingAcknowledgementBulkResultItem,
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

_item_adapter: TypeAdapter[ListingAcknowledgementRequest] = TypeAdapter(
    ListingAcknowledgementRequest
)


async def acknowledge_listings_bulk(
    session: AsyncSession,
    acknowledgements_raw: list[dict[str, Any]],
    client_id: str,
) -> ListingAcknowledgementBulkResponse:
    """
    Acknowledge flagged listings in bulk for the authenticated platform.

    Args:
        session: Async database session
        acknowledgements_raw: List of raw acknowledgement dicts from the request
        client_id: Private platform client ID from JWT token

    Returns:
        ListingAcknowledgementBulkResponse with per-item OK/NOK results
    """
    total = len(acknowledgements_raw)

    # ── Step 1: Pydantic validation (per item) ──────────────────────────
    results, valid_indexes, validated_items, client_supplied_ids = validate_items(
        acknowledgements_raw, _item_adapter, ListingAcknowledgementBulkResultItem
    )

    # ── Intra-batch duplicate handling (last-wins) ──────────────────────
    valid_indexes = last_wins(
        valid_indexes,
        lambda i: validated_items[i].listing_id,
        results,
        client_supplied_ids,
        ListingAcknowledgementBulkResultItem,
    )

    # ── Step 2 + 3: Lock the current versions of the platform's listings ─
    # A platform that never submitted a listing has no platform row: every
    # item is then "not found" and no platform row is created.
    platform = await platform_crud.get_by_client_id(session, client_id)
    current_by_id: dict[str, Listing] = {}
    if platform is not None:
        current_by_id = await listing_crud.get_current_by_listing_ids(
            session,
            [validated_items[i].listing_id for i in valid_indexes],
            platform.platform_id,
            for_update=True,
        )

    accepted: list[tuple[int, Listing]] = []
    ids_to_end: list[str] = []
    for i in valid_indexes:
        acknowledgement = validated_items[i]
        current = current_by_id.get(acknowledgement.listing_id)
        if current is None:
            results[i] = nok_item(
                ListingAcknowledgementBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=f"Listing '{acknowledgement.listing_id}' not found",
                error_type="not_found_error",
                loc=["listingId"],
            )
        elif not same_instant(current.created_at, acknowledgement.created_at):
            results[i] = nok_item(
                ListingAcknowledgementBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=not_current_message(
                    acknowledgement.listing_id, acknowledgement.created_at
                ),
                error_type="conflict_error",
                loc=["createdAt"],
            )
        elif current.status != ListingStatus.flagged:
            results[i] = nok_item(
                ListingAcknowledgementBulkResultItem,
                i,
                client_supplied_ids[i],
                msg=f"Listing '{acknowledgement.listing_id}' is not flagged (status '{current.status.value}')",
                error_type="conflict_error",
                loc=["listingId"],
            )
        else:
            ids_to_end.append(acknowledgement.listing_id)
            accepted.append((i, current))

    new_versions: list[Listing] = []
    if platform is not None:
        await listing_crud.bulk_mark_as_ended(session, ids_to_end, platform.platform_id)

        # Build after the last UPDATE: a version built earlier sits in the
        # relationship collections during autoflush without being in the session.
        batch_created_at = datetime.now(UTC)
        new_versions = [
            listing_crud.build_next_version(
                current,
                platform=platform,
                created_at=batch_created_at,
                status=ListingStatus.acknowledged,
                flags=list(current.flags),
                screened_at=current.screened_at,
                acknowledged_at=batch_created_at,
            )
            for _, current in accepted
        ]
    created = await listing_crud.bulk_create(session, new_versions)

    # ── Step 4: Feedback ────────────────────────────────────────────────
    for (i, _), listing in zip(accepted, created, strict=True):
        results[i] = ok_item(
            ListingAcknowledgementBulkResultItem, i, client_supplied_ids[i], listing
        )

    return finish(ListingAcknowledgementBulkResponse, total, results)
