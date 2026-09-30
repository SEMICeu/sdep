"""Competent authority listing endpoints for API v2: acknowledged listings in own areas."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import listing_handlers
from app.api.common.auth_dependencies import ClientDependency, RequireRoles
from app.api.common.listing_examples import (
    COUNT_LISTING_RESPONSES,
    EXAMPLE_LISTING_ACKNOWLEDGED,
    FILTERS_NOTE,
    LISTING_FIELDS_DESCRIPTION,
    PAGINATION_NOTE,
    listing_example_response,
)
from app.api.common.listing_filters import (
    AreaIdQuery,
    CreatedAtFromQuery,
    CreatedAtToQuery,
    FlagsQuery,
    PlatformIdQuery,
    parse_flags,
)
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.enums import ListingStatus
from app.schemas.listing import (
    ListingCountResponse,
    ListingFilters,
    ListingListResponse,
    ListingScope,
)

router = APIRouter(tags=["ca"])

LISTINGS_DESCRIPTION = (
    "Get the current listings in the areas of the currently authenticated competent authority that were flagged by the screening and acknowledged by the platform (fixed scope: `status` is `acknowledged`, `flags` non-empty, `acknowledgedAt` set), for enforcing the hosts. "
    f"{PAGINATION_NOTE} {FILTERS_NOTE} Use `flags` to group the work by flag code, for example first `UDS` then `EXP`.\n\n{LISTING_FIELDS_DESCRIPTION}"
)

COUNT_LISTINGS_DESCRIPTION = f"Get the count of the current acknowledged listings in the areas of the currently authenticated competent authority (optional, to support pagination). {FILTERS_NOTE}"


async def listing_filters(
    created_at_from: CreatedAtFromQuery = None,
    created_at_to: CreatedAtToQuery = None,
    area_id: AreaIdQuery = None,
    platform_id: PlatformIdQuery = None,
    flags: FlagsQuery = None,
) -> ListingFilters:
    return ListingFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        area_id=area_id,
        platform_id=platform_id,
        flags=parse_flags(flags),
    )


def _scope(client: ClientDependency) -> ListingScope:
    # Fixed per audience: own areas, acknowledged only (see docs/LISTING_FUNC.md)
    return ListingScope(
        competent_authority_client_id=client.id, status=ListingStatus.acknowledged
    )


@router.get(
    "/listings",
    response_model=ListingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the acknowledged listings in the areas of the currently authenticated competent authority",
    description=LISTINGS_DESCRIPTION,
    operation_id="getListingsByCompetentAuthorityV2",
    responses=listing_example_response(EXAMPLE_LISTING_ACKNOWLEDGED),
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_listings(
    client: ClientDependency,
    pagination: LimitedPaginationDependency,
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingListResponse:
    """
    Get the acknowledged listings in the competent authority's own areas.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority extracted from token's "client_id" claim
    """
    return await listing_handlers.list_listings(
        scope=_scope(client),
        session=session,
        offset=pagination.offset,
        limit=pagination.limit,
        filters=filters,
    )


@router.get(
    "/listings/count",
    response_model=ListingCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the count of acknowledged listings in the areas of the currently authenticated competent authority (optional, to support pagination)",
    description=COUNT_LISTINGS_DESCRIPTION,
    operation_id="countListingsByCompetentAuthorityV2",
    responses=COUNT_LISTING_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def count_listings(
    client: ClientDependency,
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingCountResponse:
    """
    Count the acknowledged listings in the competent authority's own areas.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority extracted from token's "client_id" claim
    """
    return await listing_handlers.count_listings(
        scope=_scope(client),
        session=session,
        filters=filters,
    )
