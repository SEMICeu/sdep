"""Competent authority endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_async_db_read_only
from app.schemas.activity import (
    ActivityCountResponse,
    ActivityListResponse,
    ActivityResponse,
    AddressResponse,
    TemporalResponse,
)
from app.schemas.auth import UnauthorizedError
from app.schemas.validation import HTTPBadRequestError
from app.security import verify_bearer_token
from app.services import activity

router = APIRouter(tags=["ca"])


@router.get(
    "/ca/activities",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities for the current authenticated competent authority",
    description="Get activities for the current authenticated competent authority. By default, returns all activities (unlimited). Use optional pagination parameters to limit results.\n\n"
    "**Each activity contains:**\n"
    "- `activityId`: Functional ID identifying this activity\n"
    "- `activityName`: Optional human-readable name for this activity\n"
    "- `areaId`: Functional ID referencing the area where this activity took place\n"
    "- `url`: URL of the advertisement\n"
    "- `address`: Address composite (`street`, `number`, `letter`, `addition`, `postalCode`, `city`)\n"
    "- `registrationNumber`: Registration number for the address\n"
    "- `numberOfGuests`: Number of guests (optional)\n"
    "- `countryOfGuests`: Array of country codes of guests (optional)\n"
    "- `temporal`: Temporal composite (`startDatetime`, `endDatetime`)\n"
    "- `platformId`: Functional ID identifying the platform that submitted this activity\n"
    "- `platformName`: Display name of the platform\n"
    "- `createdAt`: Timestamp when this activity version was created (UTC)\n\n"
    "**Response Codes:**\n"
    "- **200 OK:** Activities retrieved successfully\n"
    "- **401 Unauthorized:** Invalid or missing token\n"
    "- **403 Forbidden:** Missing required authorization roles",
    operation_id="getActivityByCompetentAuthority",
    responses={
        "400": {
            "model": HTTPBadRequestError,
            "description": "Bad Request - Invalid query parameters",
        },
        "401": {
            "model": UnauthorizedError,
            "description": "Unauthorized - Invalid or missing token",
        },
        "403": {
            "description": "Forbidden - Missing required authorization roles",
        },
    },
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "activities": [
                                {
                                    "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                    "activityName": "Amsterdam Summer Rental 2025",
                                    "areaId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                                    "url": "https://example.com/listing/amsterdam-001",
                                    "address": {
                                        "street": "Prinsengracht",
                                        "number": 263,
                                        "letter": "A",
                                        "addition": "2",
                                        "postalCode": "1016HV",
                                        "city": "Amsterdam",
                                    },
                                    "registrationNumber": "REG-AMS-2025-001",
                                    "numberOfGuests": 4,
                                    "countryOfGuests": ["NLD", "DEU", "BEL"],
                                    "temporal": {
                                        "startDatetime": "2025-07-01T15:00:00Z",
                                        "endDatetime": "2025-07-07T11:00:00Z",
                                    },
                                    "platformId": "sdep-test-str01",
                                    "platformName": "Example Platform",
                                    "createdAt": "2025-06-15T14:30:00Z",
                                },
                                {
                                    "activityId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                                    "activityName": "Rotterdam City Center Rental",
                                    "areaId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                                    "url": "https://example.com/listing/amsterdam-002",
                                    "address": {
                                        "street": "Keizersgracht",
                                        "number": 123,
                                        "letter": None,
                                        "addition": None,
                                        "postalCode": "1015CJ",
                                        "city": "Amsterdam",
                                    },
                                    "registrationNumber": "REG-AMS-2025-002",
                                    "numberOfGuests": 2,
                                    "countryOfGuests": ["FRA", "ITA"],
                                    "temporal": {
                                        "startDatetime": "2025-07-10T16:00:00Z",
                                        "endDatetime": "2025-07-15T12:00:00Z",
                                    },
                                    "platformId": "sdep-test-str01",
                                    "platformName": "Example Platform",
                                    "createdAt": "2025-06-16T10:15:00Z",
                                },
                            ]
                        }
                    }
                }
            }
        }
    },
)
async def get_activities(
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
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> ActivityListResponse:
    """
    Get activities for the current authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns a list of activities, each containing:
    - activityId: Functional ID
    - activityName: Optional human-readable name
    - areaId: Functional ID
    - url: URL of the advertisement
    - address: Address composite (street, number, letter, addition, postalCode, city)
    - registrationNumber: Registration number
    - numberOfGuests: Number of guests (optional)
    - countryOfGuests: Array of country codes (optional)
    - temporal: Temporal composite (startDatetime, endDatetime)
    - platformId: Platform ID
    - platformName: Platform name
    - createdAt: Creation timestamp

    Pagination parameters:
    - offset: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: no limit, max: 1000)
    """
    # Authorization check: Verify user has "sdep_ca" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract competent authority ID from token's client_id claim
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Call business service with competent authority ID from token
    activity_list = await activity.get_activity_list(
        session,
        competent_authority_id=competent_authority_id,
        offset=offset,
        limit=limit,
    )

    # Transform to API response format
    activity_responses = [
        ActivityResponse(
            activityId=activity_dict["activity_id"],
            activityName=activity_dict.get("activity_name"),
            areaId=activity_dict["area_id"],
            url=activity_dict["url"],
            address=AddressResponse(
                street=activity_dict["address_street"],
                number=activity_dict["address_number"],
                letter=activity_dict["address_letter"],
                addition=activity_dict["address_addition"],
                postalCode=activity_dict["address_postal_code"],
                city=activity_dict["address_city"],
            ),
            registrationNumber=activity_dict["registration_number"],
            numberOfGuests=activity_dict["number_of_guests"],
            countryOfGuests=activity_dict["country_of_guests"],
            temporal=TemporalResponse(
                startDatetime=activity_dict["temporal_start_date_time"],
                endDatetime=activity_dict["temporal_end_date_time"],
            ),
            platformId=activity_dict["platform_id"],
            platformName=activity_dict["platform_name"],
            createdAt=activity_dict["created_at"],
        )
        for activity_dict in activity_list
    ]

    return ActivityListResponse(activities=activity_responses)


@router.get(
    "/ca/activities/count",
    response_model=ActivityCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities count for the current authenticated competent authority (optional, to support pagination)",
    description="Get activities count for the current authenticated competent authority (optional, to support pagination)\n\n"
    "**Response Codes:**\n"
    "- **200 OK:** Count retrieved successfully\n"
    "- **401 Unauthorized:** Invalid or missing token\n"
    "- **403 Forbidden:** Missing required authorization roles",
    operation_id="countActivities",
    responses={
        "401": {
            "model": UnauthorizedError,
            "description": "Unauthorized - Invalid or missing token",
        },
        "403": {
            "description": "Forbidden - Missing required authorization roles",
        },
    },
)
async def count_activities(
    session: AsyncSession = Depends(get_async_db_read_only),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> ActivityCountResponse:
    """
    Count activities for the current authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns:
    - count: Total number of activities for the given competent authority
    """
    # Authorization check: Verify user has "sdep_ca" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract competent authority ID from token's client_id claim
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Call business service with competent authority ID from token
    total_count = await activity.count_activity_by_competent_authority(
        session, competent_authority_id
    )

    return ActivityCountResponse(count=total_count)
