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
    ActivityBulkCreate,
    ActivityRequest,
    ActivityResponse,
)
from app.schemas.activity_bulk import ActivityBulkResponse, ActivityBulkResultItem
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

# TypeAdapter for per-item validation (Validation flow Step 1)
_activity_request_adapter = TypeAdapter(ActivityRequest)


async def create_activities_bulk(
    session: AsyncSession,
    activities_raw: list[dict[str, Any]],
    client_id: str,
    platform_name: str,
) -> ActivityBulkResponse:
    """
    Create activities in bulk using Application-First Validation.

    Args:
        session: Async database session
        activities_raw: List of raw activity dicts from the request
        client_id: Private platform client ID from JWT token
        platform_name: Platform name from JWT token (client_name claim)

    Returns:
        ActivityBulkResponse with per-item OK/NOK results
    """
    total = len(activities_raw)
    # results[i] will hold the result for the item at index i
    results: list[ActivityBulkResultItem | None] = [None] * total
    # Track which indexes are still valid (not yet marked NOK)
    valid_indexes: list[int] = []
    # validated_items[i] holds the validated ActivityRequest for valid items
    validated_items: dict[int, ActivityRequest] = {}
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

            results[i] = ActivityBulkResultItem(
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

        validated_items[i] = activity_req
        valid_indexes.append(i)

    # ── Platform resolution (once per batch) ────────────────────────────
    platform = await platform_crud.get_by_client_id(session, client_id)

    if platform is None:
        # Check if deactivated
        platform_deactivated = await platform_crud.exists_any_by_client_id(
            session, client_id
        )
        if platform_deactivated:
            raise InvalidOperationError(
                f"Platform client '{client_id}' has been deactivated"
            )
        platform = await platform_crud.create(
            session=session,
            client_id=client_id,
            platform_name=platform_name,
        )
    elif platform.platform_name != platform_name:
        # Name changed in JWT claim → version: mark old as ended, create new
        public_platform_id = platform.platform_id
        await platform_crud.mark_as_ended_by_client_id(session, client_id)
        platform = await platform_crud.create(
            session=session,
            platform_id=public_platform_id,
            client_id=client_id,
            platform_name=platform_name,
        )
    # else: platform exists and name unchanged → reuse as-is

    # ── Intra-batch duplicate handling (last-wins) ──────────────────────
    # Pass 1: record the latest position for each activity_id
    activity_id_last_index: dict[str, int] = {}
    for i in valid_indexes:
        activity_id = validated_items[i].validated_activity_id
        activity_id_last_index[activity_id] = i

    # Pass 2: mark every non-final occurrence as NOK (superseded)
    for i in valid_indexes:
        last_idx = activity_id_last_index[validated_items[i].validated_activity_id]
        if i == last_idx:
            continue
        results[i] = ActivityBulkResultItem(
            activityIndex=i,
            activityId=client_supplied_ids[i],
            status="NOK",
            activity=None,
            errors=ErrorResponse(
                detail=[
                    ErrorDetail(
                        msg=f"Superseded by later item in batch at index {last_idx}",
                        type="duplicate_error",
                    )
                ]
            ),
        )

    # Rebuild valid_indexes excluding superseded items
    valid_indexes = [i for i in valid_indexes if results[i] is None]

    # ── Step 2: Referential Integrity check (single query) ──────────────
    unique_area_ids = list({validated_items[i].area_id for i in valid_indexes})
    area_ca_map = await area_crud.get_area_ca_map(session, unique_area_ids)

    still_valid: list[int] = []
    for i in valid_indexes:
        activity_req = validated_items[i]
        area_id_str = activity_req.area_id
        if area_id_str not in area_ca_map:
            results[i] = ActivityBulkResultItem(
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
    activity_ids_to_check: list[str] = []
    for i in valid_indexes:
        activity_ids_to_check.append(validated_items[i].validated_activity_id)

    if activity_ids_to_check:
        # Check for deactivated entities
        deactivated = await activity_crud.get_deactivated_activity_ids(
            session, activity_ids_to_check
        )
        if deactivated:
            still_valid = []
            for i in valid_indexes:
                aid = validated_items[i].validated_activity_id
                if aid in deactivated:
                    results[i] = ActivityBulkResultItem(
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
            validated_items[i].validated_activity_id
            for i in valid_indexes
            if validated_items[i].activity_id is not None
        ]

        if ids_for_versioning:
            current_ids = await activity_crud.get_current_by_activity_ids(
                session, ids_for_versioning, platform.id, for_update=True
            )
            ids_to_end = [aid for aid in ids_for_versioning if aid in current_ids]
            if ids_to_end:
                await activity_crud.bulk_mark_as_ended(session, ids_to_end, platform.id)

    # ── Step 3: Bulk Insert ─────────────────────────────────────────────
    # Use a single timestamp for all items in the batch
    batch_created_at = datetime.now(UTC)

    created_activity_by_index = {}
    if valid_indexes:
        activity_rows: list[ActivityBulkCreate] = []
        for i in valid_indexes:
            activity_req = validated_items[i]
            area_obj = area_ca_map[activity_req.area_id]
            activity_rows.append(
                ActivityBulkCreate(
                    **activity_req.model_dump(),
                    platform_technical_id=platform.id,
                    area_technical_id=area_obj.id,
                    created_at=batch_created_at,
                )
            )

        created_activities = await activity_crud.bulk_create(
            session, activity_rows, platform, area_ca_map
        )
        created_activity_by_index = dict(
            zip(valid_indexes, created_activities, strict=True)
        )

    # ── Step 4: Feedback ────────────────────────────────────────────────
    # Fill in OK results for valid items with embedded ActivityResponse
    for i in valid_indexes:
        activity_req = validated_items[i]
        activity_id = activity_req.validated_activity_id
        created_activity = created_activity_by_index[i]

        activity_response = ActivityResponse.model_validate(created_activity)

        results[i] = ActivityBulkResultItem(
            activityIndex=i,
            activityId=client_supplied_ids[i],
            status="OK",
            activity=activity_response,
            errors=None,
        )

    final_results: list[ActivityBulkResultItem] = [r for r in results if r is not None]
    succeeded = sum(1 for r in final_results if r.status == "OK")
    failed = total - succeeded

    return ActivityBulkResponse(
        totalReceived=total,
        succeeded=succeeded,
        failed=failed,
        results=final_results,
    )
