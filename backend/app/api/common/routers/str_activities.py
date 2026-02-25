"""STR activities endpoint.

Transaction Management Architecture (API Layer):
- This API endpoint uses get_async_db for automatic transaction management
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes, never commits

Pattern:
- API layer: Transaction boundary (auto-commit via dependency)
- Service layer: Business logic (no transaction management)
- CRUD layer: Data access (flush only, no commits)
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_async_db, get_async_db_read_only
from app.schemas.activity import (
    ActivityCountResponse,
    ActivityOwnListResponse,
    ActivityOwnResponse,
    ActivityRequest,
    AddressResponse,
    TemporalResponse,
)
from app.schemas.error import ErrorResponse
from app.security import verify_bearer_token
from app.services import activity as activity_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["str"])


@router.post(
    "/str/activities",
    summary="Submit a single activity into the activities collection for the current authenticated platform",
    description="""Submit a single activity into the activities collection for the current authenticated platform (platformId).

**ID Pattern:**
- `activityId`: provided by platform as business identifier (optional), otherwise generated as UUID (RFC 9562)

**Versioning:**
- Same `activityId` can be resubmitted → creates new version with different timestamp
- Unique constraint: (activityId, createdAt, current authenticated platform)

**The request contains:**
- `activityId`: Functional ID identifying this activity (optional, auto-generated UUID if not provided; lowercase alphanumeric with hyphens `^[a-z0-9-]+$`, max 64 chars)
- `activityName`: Optional human-readable name for this activity (optional, max 64 chars)
- `areaId`: Functional ID referencing the area where this activity took place (required; lowercase alphanumeric with hyphens `^[a-z0-9-]+$`, max 64 chars)
- `url`: URL of the advertisement (required, max 128 chars)
- `address`: Address composite (required):
  - `street`: Street name (required, max 64 chars)
  - `number`: House number (required, integer >= 1)
  - `letter`: House letter (optional, exactly 1 alphabetic char)
  - `addition`: House addition (optional, max 10 chars)
  - `postalCode`: Postal code (required, alphanumeric, no spaces, max 8 chars)
  - `city`: City name (required, max 64 chars)
- `registrationNumber`: Registration number for the address (required, max 32 chars)
- `numberOfGuests`: Number of guests (optional, integer 1-1024 when provided)
- `countryOfGuests`: Array of country codes of guests (optional, ISO 3166-1 alpha-3: exactly 3 uppercase letters per code, 1-1024 items when provided)
- `temporal`: Temporal composite (required):
  - `startDatetime`: Start date and time of the rental activity (required, year >= 2025)
  - `endDatetime`: End date and time of the rental activity (required, must be after `startDatetime`)

**The response contains:**
- `activityId`: Functional ID identifying this activity
- `activityName`: Optional human-readable name for this activity
- `areaId`: Functional ID referencing the area where this activity took place
- `competentAuthorityId`: Functional ID of the competent authority who owns the referenced area (convenience)
- `competentAuthorityName`: Display name of the competent authority (convenience)
- `url`: URL of the advertisement
- `address`: Address composite (`street`, `number`, `letter`, `addition`, `postalCode`, `city`)
- `registrationNumber`: Registration number for the address
- `numberOfGuests`: Number of guests (optional)
- `countryOfGuests`: Array of country codes of guests (optional)
- `temporal`: Temporal composite (`startDatetime`, `endDatetime`)
- `createdAt`: Timestamp when this activity version was created (UTC)

""",
    operation_id="postActivity",
    response_model=ActivityOwnResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        "201": {
            "description": "Activity created successfully",
            "model": ActivityOwnResponse,
            "content": {
                "application/json": {
                    "example": {
                        "activityId": "550e8400-e29b-41d4-a716-446655440000",
                        "activityName": "Amsterdam Summer Rental",
                        "areaId": "842be2b4-cd0c-4019-a9d5-71c9140a5eff",
                        "competentAuthorityId": "sdep-ca0363",
                        "competentAuthorityName": "Gemeente Amsterdam",
                        "url": "http://example.com/amsterdam-myhouse-1",
                        "address": {
                            "street": "Prinsengracht",
                            "number": 263,
                            "postalCode": "1016HV",
                            "city": "Amsterdam",
                        },
                        "registrationNumber": "REG0001",
                        "numberOfGuests": 4,
                        "countryOfGuests": ["NLD", "DEU", "BEL"],
                        "temporal": {
                            "startDatetime": "2025-06-01T14:00:00Z",
                            "endDatetime": "2025-06-07T11:00:00Z",
                        },
                        "createdAt": "2025-06-01T12:00:00Z",
                    }
                }
            },
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
        "422": {
            "model": ErrorResponse,
            "description": "Validation Error - busines rule violation",
        },
    },
)
async def post_activity(
    activity: ActivityRequest,
    session: AsyncSession = Depends(get_async_db),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> Response:
    """
    Submit a single rental activity.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_write" roles in realm_access
    - Platform ID extracted from token's "client_id" claim
    - Platform name extracted from token's "client_name" claim
    """

    # Authorization check: Verify user has "sdep_str" and "sdep_write" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_str" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_str' role required",
        )

    if "sdep_write" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_write' role required",
        )

    # Extract platform ID and name from token
    platform_id = token_payload.get("client_id")
    if not platform_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    platform_name = token_payload.get("client_name")
    if not platform_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_name' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convert request to service layer format
    activity_data = activity.to_service_dict(platform_id, platform_name)

    # Create activity via service layer
    activity_obj = await activity_service.create_activity(session, activity_data)

    # Eager-load area and competent_authority relationships for response building
    await session.refresh(activity_obj, ["area"])
    await session.refresh(activity_obj.area, ["competent_authority"])

    # Build response from ORM object
    response = ActivityOwnResponse(
        activityId=activity_obj.activity_id,
        activityName=activity_obj.activity_name,
        areaId=activity_obj.area.area_id,
        competentAuthorityId=activity_obj.area.competent_authority.competent_authority_id,
        competentAuthorityName=activity_obj.area.competent_authority.competent_authority_name,
        url=activity_obj.url,
        address=AddressResponse(
            street=activity_obj.address_street,
            number=activity_obj.address_number,
            letter=activity_obj.address_letter,
            addition=activity_obj.address_addition,
            postalCode=activity_obj.address_postal_code,
            city=activity_obj.address_city,
        ),
        registrationNumber=activity_obj.registration_number,
        numberOfGuests=activity_obj.number_of_guests,
        countryOfGuests=activity_obj.country_of_guests,
        temporal=TemporalResponse(
            startDatetime=activity_obj.temporal_start_date_time,
            endDatetime=activity_obj.temporal_end_date_time,
        ),
        createdAt=activity_obj.created_at,
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/str/activities",
    summary="Get activities for the current authenticated platform",
    description="""Get all activities submitted by the current authenticated platform. By default, returns all activities (unlimited). Use optional pagination parameters to limit results.

**Scoping:**
- Only returns activities belonging to the authenticated STR platform (based on JWT client_id)

**Each activity contains:**
- `activityId`: Functional ID identifying this activity
- `activityName`: Optional human-readable name for this activity
- `areaId`: Functional ID referencing the area where this activity took place
- `competentAuthorityId`: Functional ID of the competent authority who owns the referenced area (convenience)
- `competentAuthorityName`: Display name of the competent authority (convenience)
- `url`: URL of the advertisement
- `address`: Address composite (`street`, `number`, `letter`, `addition`, `postalCode`, `city`)
- `registrationNumber`: Registration number for the address
- `numberOfGuests`: Number of guests (optional)
- `countryOfGuests`: Array of country codes of guests (optional)
- `temporal`: Temporal composite (`startDatetime`, `endDatetime`)
- `createdAt`: Timestamp when this activity version was created (UTC)

**Pagination:**
- `offset`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: unlimited)

""",
    operation_id="getOwnActivities",
    response_model=ActivityOwnListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        "200": {
            "content": {
                "application/json": {
                    "example": {
                        "activities": [
                            {
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "activityName": "Amsterdam Summer Rental",
                                "areaId": "842be2b4-cd0c-4019-a9d5-71c9140a5eff",
                                "competentAuthorityId": "sdep-ca0363",
                                "competentAuthorityName": "Gemeente Amsterdam",
                                "url": "http://example.com/amsterdam-myhouse-1",
                                "address": {
                                    "street": "Prinsengracht",
                                    "number": 263,
                                    "postalCode": "1016HV",
                                    "city": "Amsterdam",
                                },
                                "registrationNumber": "REG0001",
                                "numberOfGuests": 4,
                                "countryOfGuests": ["NLD", "DEU", "BEL"],
                                "temporal": {
                                    "startDatetime": "2025-06-01T14:00:00Z",
                                    "endDatetime": "2025-06-07T11:00:00Z",
                                },
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
)
async def get_own_activities(
    session: AsyncSession = Depends(get_async_db),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
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
) -> Response:
    """
    Get activities for the current authenticated platform.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access
    - Platform ID extracted from token's "client_id" claim
    """

    # Authorization check: Verify user has "sdep_str" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_str" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_str' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract platform ID from token
    platform_id = token_payload.get("client_id")
    if not platform_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get activities for this platform
    activity_dicts = await activity_service.get_activities_by_platform(
        session,
        platform_id_str=platform_id,
        offset=offset,
        limit=limit,
    )

    # Build response
    activities = [
        ActivityOwnResponse(
            activityId=act["activity_id"],
            activityName=act["activity_name"],
            areaId=act["area_id"],
            competentAuthorityId=act["competent_authority_id"],
            competentAuthorityName=act["competent_authority_name"],
            url=act["url"],
            address=AddressResponse(
                street=act["address_street"],
                number=act["address_number"],
                letter=act["address_letter"],
                addition=act["address_addition"],
                postalCode=act["address_postal_code"],
                city=act["address_city"],
            ),
            registrationNumber=act["registration_number"],
            numberOfGuests=act["number_of_guests"],
            countryOfGuests=act["country_of_guests"],
            temporal=TemporalResponse(
                startDatetime=act["temporal_start_date_time"],
                endDatetime=act["temporal_end_date_time"],
            ),
            createdAt=act["created_at"],
        )
        for act in activity_dicts
    ]

    response = ActivityOwnListResponse(activities=activities)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/str/activities/count",
    response_model=ActivityCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get activities count for the current authenticated platform (optional, to support pagination)",
    description="Get activities count for the current authenticated platform (optional, to support pagination)",
    operation_id="countOwnActivities",
    responses={
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
    },
)
async def count_own_activities(
    session: AsyncSession = Depends(get_async_db_read_only),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> ActivityCountResponse:
    """
    Count activities for the current authenticated platform.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access
    - Platform ID extracted from token's "client_id" claim

    Returns:
    - count: Total number of activities for the given platform
    """
    # Authorization check: Verify user has "sdep_str" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_str" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_str' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract platform ID from token's client_id claim
    platform_id = token_payload.get("client_id")
    if not platform_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Call business service with platform ID from token
    total_count = await activity_service.count_activities_by_platform(
        session, platform_id
    )

    return ActivityCountResponse(count=total_count)
