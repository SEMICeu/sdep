"""Reporting (statistics office) activity endpoints for API v1."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import activity_handlers
from app.api.common.activity_examples import (
    ACTIVITY_EXAMPLE_RESPONSE,
    COUNT_ACTIVITY_RESPONSES,
)
from app.api.common.auth_dependencies import RequireRoles
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.activity import (
    ActivityCountResponse,
    ActivityFilters,
    ActivityListResponse,
)
from app.schemas.common import OptionalFunctionalId, UtcDateTime

router = APIRouter(tags=["rep"])

ACTIVITIES_DESCRIPTION = (
    "Get all current activities across all competent authorities and platforms, for statistical analysis. Returns at most 1000 activities per request (the default and maximum `limit`), including current records whose lifecycle `status` is `cancelled`. Use the `offset` and `limit` pagination parameters to page through results. Optional filters use AND semantics: every provided filter narrows the result set. `filterCreatedAtFrom` and `filterCreatedAtTo` form an inclusive `createdAt` range; `filterPlatformId`, `filterAreaId` and `filterCompetentAuthorityId` are exact-match filters.\n\n"
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

COUNT_ACTIVITIES_DESCRIPTION = "Get the count of all current activities across all competent authorities and platforms (optional, to support pagination). Counts all current activity records, including those whose lifecycle `status` is `cancelled`. Optional filters use AND semantics: every provided filter narrows the count. `filterCreatedAtFrom` and `filterCreatedAtTo` form an inclusive `createdAt` range; `filterPlatformId`, `filterAreaId` and `filterCompetentAuthorityId` are exact-match filters."


async def activity_filters(
    created_at_from: Annotated[
        UtcDateTime | None,
        Query(
            alias="filterCreatedAtFrom",
            description="Filter activities whose createdAt timestamp is greater than or equal to this UTC value",
            examples=["2025-06-01T00:00:00Z"],
        ),
    ] = None,
    created_at_to: Annotated[
        UtcDateTime | None,
        Query(
            alias="filterCreatedAtTo",
            description="Filter activities whose createdAt timestamp is less than or equal to this UTC value",
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
    competent_authority_id: Annotated[
        OptionalFunctionalId,
        Query(
            alias="filterCompetentAuthorityId",
            description="Filter by competent authority functional ID",
            examples=["c4ac8ccf-a281-5789-bad7-28dfac20ca7f"],
        ),
    ] = None,
) -> ActivityFilters:
    return ActivityFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        platform_id=platform_id,
        area_id=area_id,
        competent_authority_id=competent_authority_id,
    )


@router.get(
    "/activities",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all activities across all competent authorities and platforms",
    description=ACTIVITIES_DESCRIPTION,
    operation_id="getAllActivities",
    responses=ACTIVITY_EXAMPLE_RESPONSE,
    dependencies=[Depends(RequireRoles(Role.REP, Role.READ))],
)
async def get_activities(
    pagination: LimitedPaginationDependency,
    filters: ActivityFilters = Depends(activity_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ActivityListResponse:
    """
    Get all current activities across all competent authorities and platforms.

    Authorization:
    - Requires valid bearer token with "sdep_rep" and "sdep_read" roles in realm_access
    - Results are not scoped to the authenticated client

    Pagination parameters:
    - offset: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 1000, max: 1000)

    Filter parameters (provided filters are combined with AND semantics):
    - filterCreatedAtFrom: Minimum activity version creation timestamp, inclusive
    - filterCreatedAtTo: Maximum activity version creation timestamp, inclusive
    - filterPlatformId: Platform functional ID
    - filterAreaId: Area functional ID
    - filterCompetentAuthorityId: Competent authority functional ID
    """
    return await activity_handlers.list_activities(
        client=None,
        session=session,
        offset=pagination.offset,
        limit=pagination.limit,
        filters=filters,
    )


@router.get(
    "/activities/count",
    response_model=ActivityCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the count of all activities across all competent authorities and platforms (optional, to support pagination)",
    description=COUNT_ACTIVITIES_DESCRIPTION,
    operation_id="countAllActivities",
    responses=COUNT_ACTIVITY_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.REP, Role.READ))],
)
async def count_activities(
    filters: ActivityFilters = Depends(activity_filters),
    session: AsyncSession = Depends(get_async_db_read_only),
) -> ActivityCountResponse:
    """
    Count all current activities across all competent authorities and platforms.

    Authorization:
    - Requires valid bearer token with "sdep_rep" and "sdep_read" roles in realm_access
    - Results are not scoped to the authenticated client

    Returns:
    - count: Total number of current activities
    """
    return await activity_handlers.count_activities(
        client=None,
        session=session,
        filters=filters,
    )
