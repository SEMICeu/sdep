"""Listing monitoring authority (LMA) listing endpoints for API v2: all listings, for monitoring purposes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import listing_handlers
from app.api.common.auth_dependencies import RequireRoles
from app.api.common.listing_examples import (
    COUNT_LISTING_RESPONSES,
    EXAMPLE_LISTING_ACKNOWLEDGED,
    EXAMPLE_LISTING_PENDING,
    FILTERS_NOTE,
    LISTING_FIELDS_DESCRIPTION,
    PAGINATION_NOTE,
    listing_example_response,
)
from app.api.common.listing_filters import (
    AreaIdQuery,
    CompetentAuthorityIdQuery,
    CreatedAtFromQuery,
    CreatedAtToQuery,
    FlagsQuery,
    PlatformIdQuery,
    StatusQuery,
    parse_flags,
)
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.listing import (
    ListingCountResponse,
    ListingFilters,
    ListingListResponse,
    ListingScope,
)

router = APIRouter(tags=["lma"])

# Fixed per audience: every platform, every lifecycle status (see docs/LISTING_FUNC.md)
SCOPE = ListingScope()

LISTINGS_DESCRIPTION = (
    "Get all current listings across all platforms and competent authorities, in every lifecycle status, for monitoring purposes. "
    f"{PAGINATION_NOTE} {FILTERS_NOTE} The `status` filter narrows to one lifecycle status.\n\n{LISTING_FIELDS_DESCRIPTION}"
)

COUNT_LISTINGS_DESCRIPTION = f"Get the count of all current listings across all platforms and competent authorities (optional, to support pagination). {FILTERS_NOTE}"


async def listing_filters(
    created_at_from: CreatedAtFromQuery = None,
    created_at_to: CreatedAtToQuery = None,
    area_id: AreaIdQuery = None,
    competent_authority_id: CompetentAuthorityIdQuery = None,
    platform_id: PlatformIdQuery = None,
    flags: FlagsQuery = None,
    listing_status: StatusQuery = None,
) -> ListingFilters:
    return ListingFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        area_id=area_id,
        competent_authority_id=competent_authority_id,
        platform_id=platform_id,
        flags=parse_flags(flags),
        status=listing_status,
    )


@router.get(
    "/listings",
    response_model=ListingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all listings across all platforms and competent authorities",
    description=LISTINGS_DESCRIPTION,
    operation_id="getListingsForMonitoring",
    responses=listing_example_response(
        EXAMPLE_LISTING_ACKNOWLEDGED, EXAMPLE_LISTING_PENDING
    ),
    dependencies=[Depends(RequireRoles(Role.LMA, Role.READ))],
)
async def get_listings(
    pagination: LimitedPaginationDependency,
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingListResponse:
    """
    Get all current listings, for monitoring purposes.

    Authorization:
    - Requires valid bearer token with "sdep_lma" and "sdep_read" roles in realm_access
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
    summary="Get the count of all listings across all platforms and competent authorities (optional, to support pagination)",
    description=COUNT_LISTINGS_DESCRIPTION,
    operation_id="countListingsForMonitoring",
    responses=COUNT_LISTING_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.LMA, Role.READ))],
)
async def count_listings(
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingCountResponse:
    """
    Count all current listings, for monitoring purposes.

    Authorization:
    - Requires valid bearer token with "sdep_lma" and "sdep_read" roles in realm_access
    - Results are not scoped to the authenticated client
    """
    return await listing_handlers.count_listings(
        scope=SCOPE,
        session=session,
        filters=filters,
    )
