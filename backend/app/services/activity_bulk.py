"""Bulk activity business service.

Implements the Application-First Validation flow for bulk activity creation:

1. Pydantic Check - validate each item individually, mark failures as NOK
2. Referential Integrity Check - single SELECT for area IDs, Python dict lookup
3. Bulk Insert - single multi-row INSERT for all valid items
4. Feedback - per-item OK/NOK response preserving original order

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes (session.flush()), never commits
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import activity as activity_crud
from app.crud import area as area_crud
from app.crud import platform as platform_crud
from app.exceptions.business import InvalidOperationError
from app.schemas.activity import (
    ActivityRequest,
    ActivityResponse,
    AddressResponse,
    TemporalResponse,
)
from app.schemas.activity_bulk import BulkActivityResponse, BulkActivityResultItem
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

# TypeAdapter for per-item validation (Validation flow Step 1)
_activity_request_adapter = TypeAdapter(ActivityRequest)


async def create_activities_bulk(
    session: AsyncSession,
    activities_raw: list[dict[str, Any]],
    platform_id_str: str,
    platform_name: str,
) -> BulkActivityResponse:
    """
    Create activities in bulk using Application-First Validation.

    Args:
        session: Async database session
        activities_raw: List of raw activity dicts from the request
        platform_id_str: Platform ID string from JWT token (client_id claim)
        platform_name: Platform name from JWT token (client_name claim)

    Returns:
        BulkActivityResponse with per-item OK/NOK results
    """
    total = len(activities_raw)
    # results[i] will hold the result for the item at index i
    results: list[BulkActivityResultItem | None] = [None] * total
    # Track which indexes are still valid (not yet marked NOK)
    valid_indexes: list[int] = []
    # validated_items[i] = (ActivityRequest, service_dict) for valid items
    validated_items: dict[int, tuple[ActivityRequest, dict[str, Any]]] = {}
    # Track the original client-supplied activityId per item (before UUID generation)
    client_supplied_ids: dict[int, str | None] = {}

    # ── Step 1: Pydantic validation (per item) ──────────────────────────
    for i, raw in enumerate(activities_raw):
        # Track client-supplied activityId before any processing
        client_supplied_ids[i] = raw.get("activityId")

        try:
            activity_req = _activity_request_adapter.validate_python(raw)
        except ValidationError as e:
            # Show all validation errors so the client can fix in one go
            pydantic_errors = e.errors()
            if pydantic_errors:
                error_details = [
                    ErrorDetail(
                        msg=err.get("msg", str(e)),
                        type=err.get("type", "validation_error"),
                        loc=[str(part) for part in err.get("loc", [])] or None,
                    )
                    for err in pydantic_errors
                ]
            else:
                error_details = [ErrorDetail(msg=str(e), type="validation_error")]

            results[i] = BulkActivityResultItem(
                activityIndex=i,
                activityId=client_supplied_ids[i],
                status="NOK",
                activity=None,
                errors=ErrorResponse(detail=error_details),
            )
            continue

        # Generate activity_id if not provided
        if activity_req.activity_id is None:
            activity_req.activity_id = str(uuid.uuid4())

        service_dict = activity_req.to_service_dict(platform_id_str, platform_name)
        validated_items[i] = (activity_req, service_dict)
        valid_indexes.append(i)

    # ── Platform resolution (once per batch) ────────────────────────────
    platform = await platform_crud.get_by_platform_id(session, platform_id_str)

    if platform is None:
        # Check if deactivated
        if await platform_crud.exists_any_by_platform_id(session, platform_id_str):
            raise InvalidOperationError(
                f"Platform '{platform_id_str}' has been deactivated"
            )
        platform = await platform_crud.create(
            session=session,
            platform_id=platform_id_str,
            platform_name=platform_name,
        )
    elif platform.platform_name != platform_name:
        # Name changed in JWT claim → version: mark old as ended, create new
        await platform_crud.mark_as_ended(session, platform_id_str)
        platform = await platform_crud.create(
            session=session,
            platform_id=platform_id_str,
            platform_name=platform_name,
        )
    # else: platform exists and name unchanged → reuse as-is

    # ── Intra-batch duplicate handling (last-wins) ──────────────────────
    # Scan for duplicate activityId values; only the last occurrence proceeds
    activity_id_last_index: dict[str, int] = {}
    for i in valid_indexes:
        activity_req, _ = validated_items[i]
        aid = activity_req.activity_id
        if aid is not None:
            if aid in activity_id_last_index:
                # Mark the earlier occurrence as NOK
                earlier_idx = activity_id_last_index[aid]
                results[earlier_idx] = BulkActivityResultItem(
                    activityIndex=earlier_idx,
                    activityId=client_supplied_ids[earlier_idx],
                    status="NOK",
                    activity=None,
                    errors=ErrorResponse(
                        detail=[
                            ErrorDetail(
                                msg=f"Superseded by later item in batch at index {i}",
                                type="duplicate_error",
                            )
                        ]
                    ),
                )
            activity_id_last_index[aid] = i

    # Rebuild valid_indexes excluding superseded items
    valid_indexes = [i for i in valid_indexes if results[i] is None]

    # ── Step 2: Referential Integrity check (single query) ──────────────
    unique_area_ids = list({validated_items[i][1]["area_id"] for i in valid_indexes})
    area_ca_map = await area_crud.get_area_ca_map(session, unique_area_ids)

    still_valid: list[int] = []
    for i in valid_indexes:
        _, service_dict = validated_items[i]
        area_id_str = service_dict["area_id"]
        if area_id_str not in area_ca_map:
            results[i] = BulkActivityResultItem(
                activityIndex=i,
                activityId=client_supplied_ids[i],
                status="NOK",
                activity=None,
                errors=ErrorResponse(
                    detail=[
                        ErrorDetail(
                            msg=f"Area with areaId '{area_id_str}' not found",
                            type="not_found_error",
                            loc=["areaId"],
                        )
                    ]
                ),
            )
        else:
            still_valid.append(i)

    valid_indexes = still_valid

    # ── Activity versioning (batch UPDATE before INSERT) ────────────────
    # Collect activity_ids that might need versioning
    activity_ids_to_check = [
        validated_items[i][1]["activity_id"]
        for i in valid_indexes
        if validated_items[i][1].get("activity_id") is not None
    ]

    if activity_ids_to_check:
        # Check for deactivated entities
        deactivated = await activity_crud.get_deactivated_activity_ids(
            session, activity_ids_to_check
        )
        if deactivated:
            still_valid = []
            for i in valid_indexes:
                aid = validated_items[i][1]["activity_id"]
                if aid in deactivated:
                    results[i] = BulkActivityResultItem(
                        activityIndex=i,
                        activityId=client_supplied_ids[i],
                        status="NOK",
                        activity=None,
                        errors=ErrorResponse(
                            detail=[
                                ErrorDetail(
                                    msg=f"Activity '{aid}' has been deactivated",
                                    type="business_logic_error",
                                    loc=["activityId"],
                                )
                            ]
                        ),
                    )
                else:
                    still_valid.append(i)
            valid_indexes = still_valid

        # Find which IDs have current versions → mark as ended
        ids_for_versioning = [
            validated_items[i][1]["activity_id"]
            for i in valid_indexes
            if validated_items[i][1].get("activity_id") is not None
        ]
        if ids_for_versioning:
            current_ids = await activity_crud.get_current_by_activity_ids(
                session, ids_for_versioning, platform.id
            )
            ids_to_end = [aid for aid in ids_for_versioning if aid in current_ids]
            if ids_to_end:
                await activity_crud.bulk_mark_as_ended(session, ids_to_end, platform.id)

    # ── Step 3: Bulk Insert ─────────────────────────────────────────────
    # Use a single timestamp for all items in the batch
    batch_created_at = datetime.now(UTC)

    if valid_indexes:
        insert_dicts = []
        for i in valid_indexes:
            _, service_dict = validated_items[i]
            area_technical_id = area_ca_map[service_dict["area_id"]][0]
            insert_dicts.append(
                {
                    "activity_id": service_dict["activity_id"],
                    "activity_name": service_dict.get("activity_name"),
                    "platform_id": platform.id,
                    "area_id": area_technical_id,
                    "url": service_dict["url"],
                    "address_thoroughfare": service_dict["address_thoroughfare"],
                    "address_locator_designator_number": service_dict[
                        "address_locator_designator_number"
                    ],
                    "address_locator_designator_letter": service_dict.get(
                        "address_locator_designator_letter"
                    ),
                    "address_locator_designator_addition": service_dict.get(
                        "address_locator_designator_addition"
                    ),
                    "address_post_code": service_dict["address_post_code"],
                    "address_post_name": service_dict["address_post_name"],
                    "registration_number": service_dict["registration_number"],
                    "number_of_guests": service_dict["number_of_guests"],
                    "country_of_guests": service_dict["country_of_guests"],
                    "temporal_start_date_time": service_dict[
                        "temporal_start_date_time"
                    ],
                    "temporal_end_date_time": service_dict["temporal_end_date_time"],
                    "created_at": batch_created_at,
                }
            )

        await activity_crud.bulk_create(session, insert_dicts)

    # ── Step 4: Feedback ────────────────────────────────────────────────
    # Fill in OK results for valid items with embedded ActivityResponse
    for i in valid_indexes:
        _, service_dict = validated_items[i]
        area_id_str = service_dict["area_id"]
        _, ca_id, ca_name = area_ca_map[area_id_str]

        activity_response = ActivityResponse(
            activityId=service_dict["activity_id"],
            activityName=service_dict.get("activity_name"),
            areaId=area_id_str,
            competentAuthorityId=ca_id,
            competentAuthorityName=ca_name,
            url=service_dict["url"],
            address=AddressResponse(
                thoroughfare=service_dict["address_thoroughfare"],
                locatorDesignatorNumber=service_dict[
                    "address_locator_designator_number"
                ],
                locatorDesignatorLetter=service_dict.get(
                    "address_locator_designator_letter"
                ),
                locatorDesignatorAddition=service_dict.get(
                    "address_locator_designator_addition"
                ),
                postCode=service_dict["address_post_code"],
                postName=service_dict["address_post_name"],
            ),
            registrationNumber=service_dict["registration_number"],
            numberOfGuests=service_dict["number_of_guests"],
            countryOfGuests=service_dict["country_of_guests"],
            temporal=TemporalResponse(
                startDatetime=service_dict["temporal_start_date_time"],
                endDatetime=service_dict["temporal_end_date_time"],
            ),
            platformId=platform_id_str,
            platformName=platform_name,
            createdAt=batch_created_at,
        )

        results[i] = BulkActivityResultItem(
            activityIndex=i,
            activityId=client_supplied_ids[i],
            status="OK",
            activity=activity_response,
            errors=None,
        )

    final_results: list[BulkActivityResultItem] = [r for r in results if r is not None]
    succeeded = sum(1 for r in final_results if r.status == "OK")
    failed = total - succeeded

    return BulkActivityResponse(
        totalReceived=total,
        succeeded=succeeded,
        failed=failed,
        results=final_results,
    )
