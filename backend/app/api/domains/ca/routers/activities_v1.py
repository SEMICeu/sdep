"""Competent authority activity endpoints for API v1."""

from fastapi import APIRouter, Depends, status
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
from app.schemas.activity import ActivityCountResponse, ActivityListResponse

router = APIRouter(tags=["ca"])

ACTIVITIES_DESCRIPTION = (
    "Get activities for the currently authenticated competent authority. By default, returns all current activities (unlimited), including current records whose lifecycle `status` is `cancelled`. Use optional pagination parameters to limit results.\n\n"
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

COUNT_ACTIVITIES_DESCRIPTION = "Get activities count for the currently authenticated competent authority (optional, to support pagination). Counts all current activity records, including those whose lifecycle `status` is `cancelled`."


@router.get(
    "/activities",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities for the currently authenticated competent authority",
    description=ACTIVITIES_DESCRIPTION,
    operation_id="getActivityByCompetentAuthority",
    responses=ACTIVITY_EXAMPLE_RESPONSE,
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_activities(
    client: ClientDependency,
    pagination: PaginationDependency,
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
    """
    return await activity_handlers.list_activities(
        client=client,
        session=session,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get(
    "/activities/count",
    response_model=ActivityCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities count for the currently authenticated competent authority (optional, to support pagination)",
    description=COUNT_ACTIVITIES_DESCRIPTION,
    operation_id="countActivities",
    responses=COUNT_ACTIVITY_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def count_activities(
    client: ClientDependency,
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
    return await activity_handlers.count_activities(client=client, session=session)
