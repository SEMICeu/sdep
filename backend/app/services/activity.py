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


async def count_activity_by_competent_authority(
    session: AsyncSession,
    client_id: str,
    filters: ActivityFilters | None = None,
) -> int:
    """
    Count activities for a competent authority.

    Business logic for counting activities filtered by competent authority.

    Transaction Management:
    - Uses read-only session (no transaction needed for queries)
    - Service contains only business logic

    Args:
        session: Async database session (read-only)
        client_id: client ID from JWT
        filters: Optional activity query filters

    Returns:
        Total number of activity records for the given competent authority
    """
    return await activity_crud.count_by_competent_authority_client_id(
        session,
        client_id,
        filters=filters,
    )


async def get_activity_list(
    session: AsyncSession,
    client_id: str,
    offset: int = 0,
    limit: int | None = None,
    filters: ActivityFilters | None = None,
) -> list[Activity]:
    """
    Get activity list for a competent authority.

    Business logic for retrieving activities filtered by competent authority.
    Transaction Management:
    - Uses read-only session (no transaction needed for queries)
    - Service contains only business logic

    Args:
        session: Async database session (read-only)
        client_id: client ID from JWT
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)
        filters: Optional activity query filters

    Returns:
        List of Activity objects with platform/area relationships eagerly loaded.
    """
    return await activity_crud.get_by_competent_authority_client_id(
        session,
        client_id,
        offset=offset,
        limit=limit,
        filters=filters,
    )
