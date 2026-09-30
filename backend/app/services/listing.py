"""Listing read service.

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- CRUD layer only flushes (session.flush()), never commits
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import listing as listing_crud
from app.models.listing import Listing
from app.schemas.listing import ListingFilters, ListingScope


async def get_listing_list(
    session: AsyncSession,
    *,
    scope: ListingScope,
    offset: int = 0,
    limit: int | None = None,
    filters: ListingFilters | None = None,
) -> list[Listing]:
    """
    Get current listings within the audience scope.

    The scope is fixed by the router (a platform sees its own listings, a
    competent authority its own areas, LSA/LMA/STA everything); the filters
    come from the query string. Keyword-only, no default: an unscoped read is
    only reached by passing `ListingScope()` explicitly.

    Args:
        session: Async database session (read-only)
        scope: Fixed audience scope
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)
        filters: Optional listing query filters

    Returns:
        List of Listing objects with platform/area relationships eagerly loaded.
    """
    return await listing_crud.get_current_listings(
        session,
        scope=scope,
        offset=offset,
        limit=limit,
        filters=filters,
    )


async def count_current_listings(
    session: AsyncSession,
    *,
    scope: ListingScope,
    filters: ListingFilters | None = None,
) -> int:
    """
    Count current listings within the audience scope, see get_listing_list.

    Args:
        session: Async database session (read-only)
        scope: Fixed audience scope
        filters: Optional listing query filters

    Returns:
        Total number of current listing records within the scope.
    """
    return await listing_crud.count_current_listings(
        session,
        scope=scope,
        filters=filters,
    )
