"""Shared activity list/count endpoint behavior across API domains.

These handlers back both the CA endpoints (scoped to the authenticated competent
authority) and the REP endpoint (unscoped, across all competent authorities). The scope
is selected by the ``client`` argument: a ``Client`` scopes the read, ``None`` makes it
unscoped. ``client`` is keyword-only with no default, so an unscoped read can only be
triggered by explicitly passing ``client=None``.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import Client
from app.schemas.activity import (
    ActivityCountResponse,
    ActivityFilters,
    ActivityListResponse,
    ActivityResponse,
)
from app.services import activity


async def list_activities(
    *,
    client: Client | None,
    session: AsyncSession,
    offset: int = 0,
    limit: int | None = None,
    filters: ActivityFilters | None = None,
) -> ActivityListResponse:
    activity_objects = await activity.get_activity_list(
        session,
        client_id=client.id if client is not None else None,
        offset=offset,
        limit=limit,
        filters=filters,
    )

    return ActivityListResponse(
        activities=[
            ActivityResponse.model_validate(activity_obj)
            for activity_obj in activity_objects
        ]
    )


async def count_activities(
    *,
    client: Client | None,
    session: AsyncSession,
    filters: ActivityFilters | None = None,
) -> ActivityCountResponse:
    total_count = await activity.count_current_activities(
        session,
        client_id=client.id if client is not None else None,
        filters=filters,
    )

    return ActivityCountResponse(count=total_count)
