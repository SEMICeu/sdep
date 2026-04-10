"""STR bulk activities endpoint.

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

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import NamedClientDependency, RequireRoles
from app.api.common.security import Role
from app.db.config import get_async_db
from app.schemas.activity_bulk import (
    BulkActivityRequest,
    BulkActivityResponse,
)
from app.schemas.error import ErrorResponse
from app.services import activity_bulk as activity_bulk_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["str"])


@router.post(
    "/str/activities/bulk",
    summary="Submit activities in bulk for the current authenticated platform",
    description="""Submit up to 1000 activities in a single request for the current authenticated platform (platformId).

**Bulk processing architecture:**

At high volumes (500K-4M records/day), single-record POST creates network latency overhead
and WAL pressure. This bulk endpoint uses Application-First Validation: errors are caught
in the application layer (many times faster than database savepoints), with a single
referential integrity query per batch and a single multi-row INSERT for all valid items.

**Validation flow (4 steps):**

1. **Syntax and semantical validation** — each item is validated individually against the ActivityRequest schema.
   Failed items are marked NOK with the error reason; valid items continue.
2. **Referential Integrity Check** — area IDs are fetched in a single query and checked
   via Python dict lookup. Items with unknown areaId are marked NOK.
3. **Bulk Insert** — all remaining valid items are inserted in a single multi-row INSERT.
4. **Feedback** — per-item OK/NOK response preserving original order.

**Intra-batch duplicates (last-wins):**
When the same `activityId` appears multiple times in a single batch, only the last
occurrence is processed. Earlier occurrences receive NOK.

**Versioning:**
Existing current versions in the database are marked as ended via a single batch UPDATE
before the bulk INSERT creates new versions.

**Each activity item follows the same schema as POST /str/activities:**
- `activityId`: Functional ID (optional, auto-generated UUID if not provided)
- `activityName`: Optional human-readable name (max 64 chars)
- `areaId`: Area functional ID (required)
- `url`: URL of the advertisement (required, max 128 chars)
- `address`: Address composite (required)
- `registrationNumber`: Registration number (required, max 32 chars)
- `numberOfGuests`: Number of guests (optional, 1-1024)
- `countryOfGuests`: Array of ISO 3166-1 alpha-3 country codes (optional, 1-1024)
- `temporal`: Temporal composite (required)

**Response:**
Per-item results with summary counts. HTTP status varies:
- 201: all items created successfully
- 200: partial success (some OK, some NOK)
- 422: all items failed
""",
    operation_id="postActivitiesBulk",
    response_model=BulkActivityResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        "201": {
            "description": "All activities created successfully",
            "model": BulkActivityResponse,
            "content": {
                "application/json": {
                    "example": {
                        "totalReceived": 2,
                        "succeeded": 2,
                        "failed": 0,
                        "results": [
                            {
                                "activityIndex": 0,
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "OK",
                            },
                            {
                                "activityIndex": 1,
                                "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                "status": "OK",
                            },
                        ],
                    }
                }
            },
        },
        "200": {
            "description": "Partial success - some activities created, some failed",
            "model": BulkActivityResponse,
            "content": {
                "application/json": {
                    "example": {
                        "totalReceived": 2,
                        "succeeded": 1,
                        "failed": 1,
                        "results": [
                            {
                                "activityIndex": 0,
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "OK",
                            },
                            {
                                "activityIndex": 1,
                                "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                "status": "NOK",
                                "errorMessage": "Area with areaId 'c5f54e98-226a-411b-b015-ca13070c6dc5' not found",
                            },
                        ],
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
            "model": BulkActivityResponse,
            "description": "All activities failed validation",
        },
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "activities": [
                            {
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "activityName": "Amsterdam Summer Rental",
                                "areaId": "3ab7c2b9-5c8d-4100-bc3e-00ac115f0495",
                                "url": "http://example.com/amsterdam-myhouse-1",
                                "address": {
                                    "thoroughfare": "Prinsengracht",
                                    "locatorDesignatorNumber": 263,
                                    "locatorDesignatorLetter": "a",
                                    "locatorDesignatorAddition": "II",
                                    "postCode": "1016GV",
                                    "postName": "Amsterdam",
                                },
                                "registrationNumber": "REG0001",
                                "numberOfGuests": 4,
                                "countryOfGuests": ["NLD", "NLD", "DEU", "BEL"],
                                "temporal": {
                                    "startDatetime": "2025-06-01T14:00:00Z",
                                    "endDatetime": "2025-06-07T11:00:00Z",
                                },
                            },
                            {
                                "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                "activityName": "Rotterdam Weekend Stay",
                                "areaId": "c5f54e98-226a-411b-b015-ca13070c6dc5",
                                "url": "http://example.com/rotterdam-apartment-2",
                                "address": {
                                    "thoroughfare": "Witte de Withstraat",
                                    "locatorDesignatorNumber": 45,
                                    "postCode": "3012BK",
                                    "postName": "Rotterdam",
                                },
                                "registrationNumber": "REG0002",
                                "numberOfGuests": 2,
                                "countryOfGuests": ["FRA", "FRA"],
                                "temporal": {
                                    "startDatetime": "2025-07-12T15:00:00Z",
                                    "endDatetime": "2025-07-14T10:00:00Z",
                                },
                            },
                        ]
                    }
                }
            }
        }
    },
    dependencies=[Depends(RequireRoles(Role.STR, Role.WRITE))],
)
async def post_activities_bulk(
    request: BulkActivityRequest,
    client: NamedClientDependency,
    session: AsyncSession = Depends(get_async_db),
) -> Response:
    """
    Submit rental activities in bulk.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_write" roles in realm_access
    - Platform ID extracted from token's "client_id" claim
    - Platform name extracted from token's "client_name" claim
    """
    # Process bulk activities via service layer
    result = await activity_bulk_service.create_activities_bulk(
        session=session,
        activities_raw=request.activities,
        platform_id_str=client.id,
        platform_name=client.name,
    )

    # Determine HTTP status based on results
    if result.failed == 0:
        http_status = status.HTTP_201_CREATED
    elif result.succeeded > 0:
        http_status = status.HTTP_200_OK
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_CONTENT

    return JSONResponse(
        status_code=http_status,
        content=result.model_dump(by_alias=True, mode="json"),
    )
