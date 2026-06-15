"""Competent authority activity endpoints for API v2."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import activity_handlers
from app.api.common.activity_examples import (
    ACTIVITY_EXAMPLE_RESPONSE,
    COUNT_ACTIVITY_RESPONSES,
)
from app.api.common.auth_dependencies import ClientDependency, RequireRoles
from app.api.common.pagination import PaginationDependency
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.activity import (
    ActivityCountResponse,
    ActivityFilters,
    ActivityListResponse,
)
from app.schemas.common import OptionalFunctionalId

router = APIRouter(tags=["ca"])

ACTIVITIES_DESCRIPTION = (
    "Get activities for the currently authenticated competent authority. By default, returns all current activities (unlimited), including current records whose lifecycle `status` is `cancelled`. Use optional pagination parameters to limit results. Optional filters use AND semantics: every provided filter narrows the result set within the authenticated CA scope. `filterCreatedAtFrom` and `filterCreatedAtTo` form an inclusive `createdAt` range; `filterPlatformId` and `filterAreaId` are exact-match filters.\n\n"
    "**Each activity contains:**\n"
    "- `activityId`: Functional ID identifying this activity\n"
    "- `activityName`: Display name (optional) of the activity\n"
    "- `status`: Lifecycle status of the activity: `finished` or `cancelled`\n"
    "- `areaId`: Functional ID referencing the area where the activity took place\n"
    "- `competentAuthorityId`: Functional ID referencing the competent authority that owns the area\n"
    "- `competentAuthorityName`: Display name (optional) of the competent authority\n"
    "- `url`: URL of the originating listing/advertisement\n"
    "- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)\n"
    "- `registrationNumber`: Registration number of the address\n"
    "- `numberOfGuests`: Number of guests (1-1024)\n"
    "- `countryOfGuests`: Array of country codes of guests (each element is ISO 3166-1 alpha-3 or `N/A`; array length equals `numberOfGuests`)\n"
    "- `temporal`: Temporal composite (`startDatetime`, `endDatetime`)\n"
    "- `platformId`: Functional ID referencing the platform that owns the activity\n"
    "- `platformName`: Display name (optional) of the platform\n"
    "- `createdAt`: Timestamp when this activity version was created (UTC)"
)

COUNT_ACTIVITIES_DESCRIPTION = "Get activities count for the currently authenticated competent authority (optional, to support pagination). Counts all current activity records, including those whose lifecycle `status` is `cancelled`. Optional filters use AND semantics: every provided filter narrows the count within the authenticated CA scope. `filterCreatedAtFrom` and `filterCreatedAtTo` form an inclusive `createdAt` range; `filterPlatformId` and `filterAreaId` are exact-match filters."


async def activity_filters(
    created_at_from: Annotated[
        datetime | None,
        Query(
            alias="filterCreatedAtFrom",
            description="Filter activities whose createdAt timestamp is greater than or equal to this value",
            examples=["2025-06-01T00:00:00Z"],
        ),
    ] = None,
    created_at_to: Annotated[
        datetime | None,
        Query(
            alias="filterCreatedAtTo",
            description="Filter activities whose createdAt timestamp is less than or equal to this value",
            examples=["2025-06-30T23:59:59Z"],
        ),
    ] = None,
    platform_id: Annotated[
        OptionalFunctionalId,
        Query(
            alias="filterPlatformId",
            description="Filter by platform functional ID",
            examples=["sdep-str01"],
        ),
    ] = None,
    area_id: Annotated[
        OptionalFunctionalId,
        Query(
            alias="filterAreaId",
            description="Filter by area functional ID",
            examples=["959a7439-7cad-4009-96ec-353b44723db9"],
        ),
    ] = None,
) -> ActivityFilters:
    return ActivityFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        platform_id=platform_id,
        area_id=area_id,
    )


@router.get(
    "/activities",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities for the currently authenticated competent authority",
    description=ACTIVITIES_DESCRIPTION,
    operation_id="getActivityByCompetentAuthorityV2",
    responses=ACTIVITY_EXAMPLE_RESPONSE,
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_activities(
    client: ClientDependency,
    pagination: PaginationDependency,
    filters: ActivityFilters = Depends(activity_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ActivityListResponse:
    """
    Get activities for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Pagination parameters:
    - offset: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: no limit, max: 1000)

    Filter parameters (provided filters are combined with AND semantics):
    - filterCreatedAtFrom: Minimum activity version creation timestamp, inclusive
    - filterCreatedAtTo: Maximum activity version creation timestamp, inclusive
    - filterPlatformId: Platform functional ID
    - filterAreaId: Area functional ID
    """
    return await activity_handlers.list_activities(
        client=client,
        session=session,
        offset=pagination.offset,
        limit=pagination.limit,
        filters=filters,
    )


@router.get(
    "/activities/count",
    response_model=ActivityCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities count for the currently authenticated competent authority (optional, to support pagination)",
    description=COUNT_ACTIVITIES_DESCRIPTION,
    operation_id="countActivitiesV2",
    responses=COUNT_ACTIVITY_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def count_activities(
    client: ClientDependency,
    filters: ActivityFilters = Depends(activity_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ActivityCountResponse:
    """
    Count activities for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns:
    - count: Total number of activities for the given competent authority
    """
    return await activity_handlers.count_activities(
        client=client,
        session=session,
        filters=filters,
    )
