"""Activity business service.

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes (session.flush()), never commits

Pattern:
- API layer: Transaction boundary (auto-commit via dependency)
- Service layer: Business logic (no transaction management)
- CRUD layer: Data access (flush only, no commits)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import activity as activity_crud
from app.models.activity import Activity
from app.schemas.activity import ActivityFilters


async def count_activity(session: AsyncSession) -> int:
    """
    Count all activities.

    Args:
        session: Async database session

    Returns:
        Total number of activity records
    """
    return await activity_crud.count(session)


async def get_activity_list(
    session: AsyncSession,
    *,
    client_id: str | None,
    offset: int = 0,
    limit: int | None = None,
    filters: ActivityFilters | None = None,
) -> list[Activity]:
    """
    Get current activities, optionally scoped to one competent authority.

    Business logic for retrieving current activities. When client_id is provided the
    result is restricted to that competent authority (CA API); when client_id is None the
    result spans all competent authorities (the unscoped reporting/REP read).

    Transaction Management:
    - Uses read-only session (no transaction needed for queries)
    - Service contains only business logic

    Args:
        session: Async database session (read-only)
        client_id: Competent-authority client ID from the JWT, or None for an unscoped read.
            Keyword-only with no default so callers must pass it explicitly.
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)
        filters: Optional activity query filters

    Returns:
        List of Activity objects with platform/area relationships eagerly loaded.
    """
    return await activity_crud.get_current_activities(
        session,
        client_id=client_id,
        offset=offset,
        limit=limit,
        filters=filters,
    )


async def count_current_activities(
    session: AsyncSession,
    *,
    client_id: str | None,
    filters: ActivityFilters | None = None,
) -> int:
    """
    Count current activities, optionally scoped to one competent authority.

    When client_id is provided the count is restricted to that competent authority (CA
    API); when client_id is None it spans all competent authorities (reporting/REP read).

    Transaction Management:
    - Uses read-only session (no transaction needed for queries)
    - Service contains only business logic

    Args:
        session: Async database session (read-only)
        client_id: Competent-authority client ID from the JWT, or None for an unscoped count.
            Keyword-only with no default so callers must pass it explicitly.
        filters: Optional activity query filters

    Returns:
        Total number of current activity records, restricted to the client when given.
    """
    return await activity_crud.count_current_activities(
        session,
        client_id=client_id,
        filters=filters,
    )
