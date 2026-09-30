"""Shared building blocks for the three listing bulk services.

Each service implements the same four-step flow as the activity bulk service
(per-item Pydantic check, referential integrity, versioning under lock,
per-item feedback). The pieces that do not depend on the write live here.
"""

from collections.abc import Callable, Hashable, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.models.listing import Listing
from app.schemas.error import ErrorDetail, ErrorResponse
from app.schemas.listing import ListingResponse
from app.schemas.listing_bulk import ListingBulkResponse, ListingBulkResultItem


def nok_item[ResultT: ListingBulkResultItem](
    result_cls: type[ResultT],
    index: int,
    listing_id: str | None,
    *,
    msg: str,
    error_type: str,
    loc: list[str | int] | None = None,
) -> ResultT:
    """Build a NOK result item with one error detail."""
    return result_cls(
        listingIndex=index,
        listingId=listing_id,
        status="NOK",
        listing=None,
        errors=ErrorResponse(detail=[ErrorDetail(msg=msg, type=error_type, loc=loc)]),
    )


def ok_item[ResultT: ListingBulkResultItem](
    result_cls: type[ResultT],
    index: int,
    listing_id: str | None,
    listing: Listing,
) -> ResultT:
    """Build an OK result item embedding the listing as it now is."""
    return result_cls(
        listingIndex=index,
        listingId=listing_id,
        status="OK",
        listing=ListingResponse.model_validate(listing),
        errors=None,
    )


def validate_items[ItemT, ResultT: ListingBulkResultItem](
    raw_items: list[dict[str, Any]],
    adapter: TypeAdapter[ItemT],
    result_cls: type[ResultT],
) -> tuple[list[ResultT | None], list[int], dict[int, ItemT], dict[int, str | None]]:
    """Validation flow Step 1: validate each item individually.

    Returns the results list (NOK filled in for invalid items), the indexes that
    are still valid, the validated items by index, and the client-supplied
    `listingId` by index (kept for the feedback even when the item is invalid).
    """
    results: list[ResultT | None] = [None] * len(raw_items)
    valid_indexes: list[int] = []
    validated_items: dict[int, ItemT] = {}
    client_supplied_ids: dict[int, str | None] = {}

    for i, raw in enumerate(raw_items):
        client_supplied_ids[i] = raw.get("listingId") if isinstance(raw, dict) else None
        try:
            validated_items[i] = adapter.validate_python(raw)
        except ValidationError as e:
            # Show all validation errors so the client can fix in one go
            details = [
                ErrorDetail(
                    msg=err.get("msg", str(e)),
                    type=err.get("type", "validation_error"),
                    loc=[str(part) for part in err.get("loc", [])] or None,
                )
                for err in e.errors()
            ] or [ErrorDetail(msg=str(e), type="validation_error")]
            results[i] = result_cls(
                listingIndex=i,
                listingId=client_supplied_ids[i],
                status="NOK",
                listing=None,
                errors=ErrorResponse(detail=details),
            )
            continue
        valid_indexes.append(i)

    return results, valid_indexes, validated_items, client_supplied_ids


def last_wins[ResultT: ListingBulkResultItem](
    valid_indexes: list[int],
    key_of: Callable[[int], Hashable],
    results: list[ResultT | None],
    client_supplied_ids: dict[int, str | None],
    result_cls: type[ResultT],
) -> list[int]:
    """Intra-batch duplicates: only the last occurrence of a key is processed.

    Earlier occurrences are marked NOK (`duplicate_error`). Returns the
    remaining valid indexes.
    """
    last_index: dict[Hashable, int] = {}
    for i in valid_indexes:
        last_index[key_of(i)] = i
    for i in valid_indexes:
        last_idx = last_index[key_of(i)]
        if i != last_idx:
            results[i] = nok_item(
                result_cls,
                i,
                client_supplied_ids[i],
                msg=f"Superseded by later item in batch at index {last_idx}",
                error_type="duplicate_error",
            )
    return [i for i in valid_indexes if results[i] is None]


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; they were stored as UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def same_instant(stored: datetime, supplied: datetime) -> bool:
    """Compare the stored version timestamp with the client's version token."""
    return _as_utc(stored) == _as_utc(supplied)


def not_current_message(listing_id: str, supplied: datetime) -> str:
    """Message for a stale version token (Concurrency, docs/LISTING_FUNC.md)."""
    token = _as_utc(supplied).isoformat().replace("+00:00", "Z")
    return f"Listing '{listing_id}' version '{token}' is no longer current"


def finish[ResponseT: ListingBulkResponse](
    response_cls: type[ResponseT],
    total: int,
    results: Sequence[ListingBulkResultItem | None],
) -> ResponseT:
    """Validation flow Step 4: the per-item results with summary counts."""
    final_results = [r for r in results if r is not None]
    succeeded = sum(1 for r in final_results if r.status == "OK")
    return response_cls(
        totalReceived=total,
        succeeded=succeeded,
        failed=total - succeeded,
        results=final_results,
    )
