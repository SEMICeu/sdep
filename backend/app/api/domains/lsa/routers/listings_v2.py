"""Listing screening authority (LSA) read endpoints for API v2: listings awaiting screening."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import listing_handlers
from app.api.common.auth_dependencies import RequireRoles
from app.api.common.listing_examples import (
    COUNT_LISTING_RESPONSES,
    EXAMPLE_LISTING_PENDING,
    listing_example_response,
)
from app.api.common.listing_filters import (
    AreaIdQuery,
    CompetentAuthorityIdQuery,
    CreatedAtFromQuery,
    CreatedAtToQuery,
    PlatformIdQuery,
)
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.api.domains.lsa.routers.listings_docs import (
    COUNT_LISTINGS_DESCRIPTION,
    COUNT_LISTINGS_SUMMARY,
    LISTINGS_DESCRIPTION,
    LISTINGS_SUMMARY,
)
from app.db.config import get_async_db_read_only
from app.enums import ListingStatus
from app.schemas.listing import (
    ListingCountResponse,
    ListingFilters,
    ListingListResponse,
    ListingScope,
)

router = APIRouter(tags=["lsa"])

# Fixed per audience: every platform, pending only (see docs/LISTING_FUNC.md)
SCOPE = ListingScope(status=ListingStatus.pending)


async def listing_filters(
    created_at_from: CreatedAtFromQuery = None,
    created_at_to: CreatedAtToQuery = None,
    area_id: AreaIdQuery = None,
    competent_authority_id: CompetentAuthorityIdQuery = None,
    platform_id: PlatformIdQuery = None,
) -> ListingFilters:
    return ListingFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        area_id=area_id,
        competent_authority_id=competent_authority_id,
        platform_id=platform_id,
    )


@router.get(
    "/listings",
    response_model=ListingListResponse,
    status_code=status.HTTP_200_OK,
    summary=LISTINGS_SUMMARY,
    description=LISTINGS_DESCRIPTION,
    operation_id="getListingsForScreening",
    responses=listing_example_response(EXAMPLE_LISTING_PENDING),
    dependencies=[Depends(RequireRoles(Role.LSA, Role.READ))],
)
async def get_listings(
    pagination: LimitedPaginationDependency,
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingListResponse:
    """
    Get the listings awaiting screening, across all platforms.

    Authorization:
    - Requires valid bearer token with "sdep_lsa" and "sdep_read" roles in realm_access
    - Results are not scoped to the authenticated client
    """
    return await listing_handlers.list_listings(
        scope=SCOPE,
        session=session,
        offset=pagination.offset,
        limit=pagination.limit,
        filters=filters,
    )


@router.get(
    "/listings/count",
    response_model=ListingCountResponse,
    status_code=status.HTTP_200_OK,
    summary=COUNT_LISTINGS_SUMMARY,
    description=COUNT_LISTINGS_DESCRIPTION,
    operation_id="countListingsForScreening",
    responses=COUNT_LISTING_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.LSA, Role.READ))],
)
async def count_listings(
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingCountResponse:
    """
    Count the listings awaiting screening, across all platforms.

    Authorization:
    - Requires valid bearer token with "sdep_lsa" and "sdep_read" roles in realm_access
    - Results are not scoped to the authenticated client
    """
    return await listing_handlers.count_listings(
        scope=SCOPE,
        session=session,
        filters=filters,
    )
