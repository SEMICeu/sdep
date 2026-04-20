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
    description="""Submit 1-1000 activities into the activities collection for the current authenticated platform (platformId).

**ID pattern:**

`activityId` is provided by the platform as a business identifier (optional).
If not provided (or empty string), a UUID is auto-generated (RFC 9562).

**Versioning:**

The same `activityId` can be resubmitted - this creates a new version with a different timestamp.
Unique constraint: (`activityId`, `createdAt`, current authenticated platform).

**Validation flow (4 steps):**

1. **Syntax and semantical validation** - each item is validated individually.
   Failed items are marked NOK with the error reason; valid items continue.
2. **Referential Integrity Check** - area IDs are verified. Items with unknown `areaId` are marked NOK; valid items continue.
3. **Bulk Insert** - all remaining valid items are inserted in a single multi-row INSERT.
4. **Feedback** - per-item OK/NOK response preserving original order.

**Intra-batch duplicates (last-wins):**
When the same `activityId` appears multiple times in a single batch, only the last
occurrence is processed. Earlier occurrences receive NOK.

**The request contains:**
- `activities`: Array of activity objects to process (1-1000 items per batch)

**Each activity item in the request contains:**
- `activityId`: Functional ID identifying the activity (optional, auto-generated UUID if not provided; alphanumeric with hyphens `^[A-Za-z0-9-]+$`, max 64 chars)
- `activityName`: Display name of the activity (optional, max 64 chars)
- `areaId`: Functional ID referencing the area where the activity took place
- `url`: URL of the originating listing/advertisement (max 128 chars)
- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber`, `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`)
- `registrationNumber`: Registration number (max 32 chars)
- `numberOfGuests`: Number of guests (optional, 1-1024)
- `countryOfGuests`: Array of ISO 3166-1 alpha-3 country codes (optional, 1-1024)
- `temporal`: Temporal composite (`startDatetime`, `endDatetime`)

**The response contains:**
- `totalReceived`: Total number of items received in the request
- `succeeded`: Number of items successfully created (status OK)
- `failed`: Number of items that failed validation or processing (status NOK)
- `results`: Per-item results preserving the original request order

**Each results item contains:**
- `activityIndex`: Zero-based index of this item in the original request list
- `activityId`: Activity functional ID provided by the client in the request
- `status`: Processing result - `OK` (created successfully) or `NOK` (failed validation or processing)
- `activity`: The full activity object (present for OK items, omitted for NOK items)
- `errors`: Structured error details (present for NOK items, omitted for OK items)

**The `activity` object (for the OK items) contains:**
- `activityId`: Functional ID identifying this activity
- `activityName`: Display name (optional) of the activity
- `areaId`: Functional ID referencing the area where this activity took place
- `competentAuthorityId`: Functional ID of the competent authority who owns the referenced area (convenience)
- `competentAuthorityName`: Display name (optional) of the competent authority
- `url`: URL of the originating listing/advertisement
- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber`, `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`)
- `registrationNumber`: Registration number for the address
- `numberOfGuests`: Number of guests (optional)
- `countryOfGuests`: Array of country codes of guests (optional)
- `temporal`: Temporal composite (startDatetime, endDatetime)
- `platformId`: Functional ID referencing the platform that owns the activity
- `platformName`: Display name (optional) of the platform
- `createdAt`: Timestamp when this activity version was created (UTC)

**Response HTTP status:**
- 201: all items created successfully
- 200: partial success (some OK, some NOK)
- 401: missing or invalid token
- 403: insufficient permissions
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
                                "activity": {
                                    "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                    "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
                                    "competentAuthorityId": "sdep-ca0363",
                                    "competentAuthorityName": "Gemeente Amsterdam",
                                    "url": "http://example.com/amsterdam-myhouse-1",
                                    "address": {
                                        "thoroughfare": "Prinsengracht",
                                        "locatorDesignatorNumber": 263,
                                        "postCode": "1016GV",
                                        "postName": "Amsterdam",
                                    },
                                    "registrationNumber": "REG0001",
                                    "numberOfGuests": 4,
                                    "countryOfGuests": ["NLD", "DEU", "BEL", "N/A"],
                                    "temporal": {
                                        "startDatetime": "2025-06-01T14:00:00Z",
                                        "endDatetime": "2025-06-07T11:00:00Z",
                                    },
                                    "platformId": "str01",
                                    "platformName": "Test STR 01",
                                    "createdAt": "2025-06-01T12:00:00Z",
                                },
                            },
                            {
                                "activityIndex": 1,
                                "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                "status": "OK",
                                "activity": {
                                    "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                    "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
                                    "competentAuthorityId": "sdep-ca0363",
                                    "competentAuthorityName": "Gemeente Amsterdam",
                                    "url": "http://example.com/amsterdam-myhouse-2",
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
                                    "platformId": "str01",
                                    "platformName": "Test STR 01",
                                    "createdAt": "2025-06-01T12:00:00Z",
                                },
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
                        "totalReceived": 4,
                        "succeeded": 2,
                        "failed": 2,
                        "results": [
                            {
                                "activityIndex": 0,
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "OK",
                                "activity": {
                                    "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                    "activityName": "Amsterdam Summer Rental",
                                    "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
                                    "competentAuthorityId": "sdep-ca0363",
                                    "competentAuthorityName": "Amsterdam (inclusief Weesp)",
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
                                    "platformId": "sdep-str01",
                                    "platformName": "Test STR 01 (interactive usage, persistent)",
                                    "createdAt": "2026-04-17T12:31:45.492466Z",
                                },
                            },
                            {
                                "activityIndex": 1,
                                "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                "status": "OK",
                                "activity": {
                                    "activityName": "Rotterdam Weekend Stay",
                                    "areaId": "904ee15d-70a6-4e69-a704-6018646803a8",
                                    "competentAuthorityId": "sdep-ca0599",
                                    "competentAuthorityName": "Rotterdam",
                                    "url": "http://example.com/rotterdam-apartment-2",
                                    "address": {
                                        "thoroughfare": "Witte de Withstraat",
                                        "locatorDesignatorNumber": 45,
                                        "locatorDesignatorLetter": None,
                                        "locatorDesignatorAddition": None,
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
                                    "platformId": "sdep-str01",
                                    "platformName": "Test STR 01 (interactive usage, persistent)",
                                    "createdAt": "2026-04-17T12:31:45.492466Z",
                                },
                            },
                            {
                                "activityIndex": 2,
                                "activityId": "771a0622-g41d-63f6-c938-668877662222",
                                "status": "NOK",
                                "errors": {
                                    "detail": [
                                        {
                                            "msg": "Value error, End datetime must be after start datetime",
                                            "type": "value_error",
                                            "loc": ["temporal", "endDatetime"],
                                        }
                                    ]
                                },
                            },
                            {
                                "activityIndex": 3,
                                "activityId": None,
                                "status": "NOK",
                                "errors": {
                                    "detail": [
                                        {
                                            "msg": "Field required",
                                            "type": "missing",
                                            "loc": ["temporal"],
                                        }
                                    ]
                                },
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
            "content": {
                "application/json": {
                    "example": {
                        "totalReceived": 2,
                        "succeeded": 0,
                        "failed": 2,
                        "results": [
                            {
                                "activityIndex": 0,
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "NOK",
                                "errors": {
                                    "detail": [
                                        {
                                            "msg": "Area with areaId 'c5f54e98-226a-411b-b015-ca13070c6dc5' not found",
                                            "type": "not_found_error",
                                            "loc": ["areaId"],
                                        },
                                        {
                                            "msg": "Value error, End datetime must be after start datetime",
                                            "type": "value_error",
                                            "loc": [
                                                "temporal",
                                                "endDatetime",
                                            ],
                                        },
                                    ]
                                },
                            },
                            {
                                "activityIndex": 1,
                                "status": "NOK",
                                "errors": {
                                    "detail": [
                                        {
                                            "msg": "Area with areaId 'c5f54e98-226a-411b-b015-ca13070c6dc5' not found",
                                            "type": "not_found_error",
                                            "loc": ["areaId"],
                                        },
                                        {
                                            "msg": "Field required",
                                            "type": "missing",
                                            "loc": ["temporal"],
                                        },
                                    ]
                                },
                            },
                        ],
                    }
                }
            },
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
                                "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
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
                                "activityName": "Rotterdam Weekend Stay",
                                "areaId": "904ee15d-70a6-4e69-a704-6018646803a8",
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
                            {
                                "activityId": "771a0622-g41d-63f6-c938-668877662222",
                                "activityName": "Utrecht City Break",
                                "areaId": "c5f54e98-226a-411b-b015-ca13070c6dc5",
                                "url": "http://example.com/utrecht-studio-3",
                                "address": {
                                    "thoroughfare": "Oudegracht",
                                    "locatorDesignatorNumber": 100,
                                    "postCode": "3511AX",
                                    "postName": "Utrecht",
                                },
                                "registrationNumber": "REG0003",
                                "numberOfGuests": 3,
                                "countryOfGuests": ["GBR", "GBR", "IRL"],
                                "temporal": {
                                    "startDatetime": "2025-08-10T11:00:00Z",
                                    "endDatetime": "2025-08-05T14:00:00Z",
                                },
                            },
                            {
                                "activityName": "Den Haag Apartment",
                                "areaId": "c5f54e98-226a-411b-b015-ca13070c6dc5",
                                "url": "http://example.com/denhaag-apartment-4",
                                "address": {
                                    "thoroughfare": "Turfmarkt",
                                    "locatorDesignatorNumber": 147,
                                    "postCode": "2500EA",
                                    "postName": "Den Haag",
                                },
                                "registrationNumber": "REG0004",
                                "numberOfGuests": 1,
                                "countryOfGuests": ["ESP"],
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
