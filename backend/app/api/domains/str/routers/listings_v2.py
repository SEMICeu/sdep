"""STR v2 listing read endpoints: the platform's flagged listings."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import listing_handlers
from app.api.common.auth_dependencies import ClientDependency, RequireRoles
from app.api.common.listing_examples import (
    COUNT_LISTING_RESPONSES,
    EXAMPLE_LISTING_FLAGGED,
    listing_example_response,
)
from app.api.common.listing_filters import (
    AreaIdQuery,
    CompetentAuthorityIdQuery,
    CreatedAtFromQuery,
    CreatedAtToQuery,
)
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.api.domains.str.routers.listings_docs import (
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

router = APIRouter(tags=["str"])


async def listing_filters(
    created_at_from: CreatedAtFromQuery = None,
    created_at_to: CreatedAtToQuery = None,
    area_id: AreaIdQuery = None,
    competent_authority_id: CompetentAuthorityIdQuery = None,
) -> ListingFilters:
    return ListingFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        area_id=area_id,
        competent_authority_id=competent_authority_id,
    )


def _scope(client: ClientDependency) -> ListingScope:
    # Fixed per audience: own listings, flagged only (see docs/LISTING_FUNC.md)
    return ListingScope(platform_client_id=client.id, status=ListingStatus.flagged)


@router.get(
    "/listings",
    response_model=ListingListResponse,
    status_code=status.HTTP_200_OK,
    summary=LISTINGS_SUMMARY,
    description=LISTINGS_DESCRIPTION,
    operation_id="getListingsV2",
    responses=listing_example_response(EXAMPLE_LISTING_FLAGGED),
    dependencies=[Depends(RequireRoles(Role.STR, Role.READ))],
)
async def get_listings(
    client: ClientDependency,
    pagination: LimitedPaginationDependency,
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingListResponse:
    """
    Get the flagged listings of the currently authenticated platform.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access
    - Platform extracted from token's "client_id" claim
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
    summary=COUNT_LISTINGS_SUMMARY,
    description=COUNT_LISTINGS_DESCRIPTION,
    operation_id="countListingsV2",
    responses=COUNT_LISTING_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.STR, Role.READ))],
)
async def count_listings(
    client: ClientDependency,
    filters: ListingFilters = Depends(listing_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ListingCountResponse:
    """
    Count the flagged listings of the currently authenticated platform.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access
    - Platform extracted from token's "client_id" claim
    """
    return await listing_handlers.count_listings(
        scope=_scope(client),
        session=session,
        filters=filters,
    )
