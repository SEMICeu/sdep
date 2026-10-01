"""Shared listing list/count endpoint behaviour across API domains.

One read handler serves every audience (STR, LSA, CA, LMA, STA). The router
fixes the ``scope`` (owner and/or lifecycle status, see ``ListingScope``); the
query string supplies the ``filters``. ``scope`` is keyword-only with no
default, so an unscoped read can only be triggered by passing ``ListingScope()``
explicitly.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.listing import (
    ListingCountResponse,
    ListingFilters,
    ListingListResponse,
    ListingResponse,
    ListingScope,
)
from app.services import listing


async def list_listings(
    *,
    scope: ListingScope,
    session: AsyncSession,
    offset: int = 0,
    limit: int | None = None,
    filters: ListingFilters | None = None,
) -> ListingListResponse:
    listing_objects = await listing.get_listing_list(
        session,
        scope=scope,
        offset=offset,
        limit=limit,
        filters=filters,
    )
    return ListingListResponse(
        listings=[ListingResponse.model_validate(obj) for obj in listing_objects]
    )


async def count_listings(
    *,
    scope: ListingScope,
    session: AsyncSession,
    filters: ListingFilters | None = None,
) -> ListingCountResponse:
    total_count = await listing.count_current_listings(
        session,
        scope=scope,
        filters=filters,
    )
    return ListingCountResponse(count=total_count)
