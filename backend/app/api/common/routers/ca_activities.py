"""Competent authority endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import ClientDependency, RequireRoles
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.activity import (
    ActivityCountResponse,
    ActivityListResponse,
    ActivityResponse,
)
from app.schemas.error import ErrorResponse
from app.services import activity

router = APIRouter(tags=["ca"])


@router.get(
    "/activities",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities for the currently authenticated competent authority",
    description="Get activities for the currently authenticated competent authority. By default, returns all current activities (unlimited), including current records whose lifecycle `status` is `cancelled`. Use optional pagination parameters to limit results.\n\n"
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
    "- `createdAt`: Timestamp when this activity version was created (UTC)",
    operation_id="getActivityByCompetentAuthority",
    responses={
        "200": {
            "content": {
                "application/json": {
                    "example": {
                        "activities": [
                            {
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "activityName": "Amsterdam Summer Rental",
                                "status": "finished",
                                "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
                                "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
                                "competentAuthorityName": "Gemeente Amsterdam",
                                "url": "http://example.com/amsterdam-myhouse-1",
                                "address": {
                                    "thoroughfare": "Prinsengracht",
                                    "locatorDesignatorNumber": 263,
                                    "postCode": "1016GV",
                                    "postName": "Amsterdam",
                                    "fullAddress": "Prinsengracht 263, 1016GV Amsterdam",
                                },
                                "registrationNumber": "REG0001",
                                "numberOfGuests": 4,
                                "countryOfGuests": ["NLD", "DEU", "BEL", "N/A"],
                                "temporal": {
                                    "startDatetime": "2025-06-01T14:00:00Z",
                                    "endDatetime": "2025-06-07T11:00:00Z",
                                },
                                "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
                                "platformName": "Test STR 01 (interactive usage, persistent)",
                                "createdAt": "2025-06-01T12:00:00Z",
                            }
                        ]
                    }
                }
            }
        },
        "400": {
            "model": ErrorResponse,
            "description": "Bad request - invalid query parameters",
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
    },
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_activities(
    client: ClientDependency,
    offset: Annotated[
        int, Query(ge=0, description="Number of records to skip (default: 0)")
    ] = 0,
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=1000,
            description="Maximum number of records to return (default: unlimited, max: 1000 when specified)",
        ),
    ] = None,
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
    activity_objects = await activity.get_activity_list(
        session,
        client_id=client.id,
        offset=offset,
        limit=limit,
    )

    activity_responses = [
        ActivityResponse.model_validate(activity_obj)
        for activity_obj in activity_objects
    ]

    return ActivityListResponse(activities=activity_responses)


@router.get(
    "/activities/count",
    response_model=ActivityCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities count for the currently authenticated competent authority (optional, to support pagination)",
    description="Get activities count for the currently authenticated competent authority (optional, to support pagination). Counts all current activity records, including those whose lifecycle `status` is `cancelled`.",
    operation_id="countActivities",
    responses={
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
    },
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
    # Call business service with competent authority ID from token
    total_count = await activity.count_activity_by_competent_authority(
        session, client.id
    )

    return ActivityCountResponse(count=total_count)
