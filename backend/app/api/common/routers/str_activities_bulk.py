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
from typing import Any, cast

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import NamedClientDependency, RequireRoles
from app.api.common.security import Role
from app.db.config import get_async_db
from app.schemas.activity_bulk import (
    ActivityBulkRequest,
    ActivityBulkResponse,
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
- `activityId`: Functional ID identifying the activity (auto-generated UUID if not provided; alphanumeric with hyphens `^[A-Za-z0-9-]+$`, max 64 chars)
- `activityName`: Display name of the activity (optional, max 64 chars)
- `status`: Lifecycle status of the activity record. Defaults to `finished` when omitted; may also be `cancelled`
- `areaId`: Functional ID referencing the area where the activity took place
- `url`: URL of the originating listing/advertisement (max 128 chars)
- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)
- `registrationNumber`: Registration number (max 32 chars)
- `numberOfGuests`: Number of guests (1-1024)
- `countryOfGuests`: Array of country codes (1-1024; each element is ISO 3166-1 alpha-3 or `N/A`, uppercase only). Its length **must equal** `numberOfGuests`.
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
- `status`: Lifecycle status of the activity record: `finished` or `cancelled`
- `areaId`: Functional ID referencing the area where this activity took place
- `competentAuthorityId`: Functional ID of the competent authority who owns the referenced area
- `competentAuthorityName`: Display name (optional) of the competent authority
- `url`: URL of the originating listing/advertisement
- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)
- `registrationNumber`: Registration number for the address
- `numberOfGuests`: Number of guests (1-1024)
- `countryOfGuests`: Array of country codes of guests (each element is ISO 3166-1 alpha-3 or `N/A`). Length equals `numberOfGuests`.
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
    response_model=ActivityBulkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        "201": {
            "description": "All activities created successfully",
            "model": ActivityBulkResponse,
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
                                    "status": "finished",
                                    "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
                                    "competentAuthorityId": "sdep-ca0363",
                                    "competentAuthorityName": "Amsterdam (inclusief Weesp)",
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
                                    "status": "cancelled",
                                    "areaId": "904ee15d-70a6-4e69-a704-6018646803a8",
                                    "competentAuthorityId": "sdep-ca0599",
                                    "competentAuthorityName": "Rotterdam",
                                    "url": "http://example.com/rotterdam-apartment-2",
                                    "address": {
                                        "thoroughfare": "Witte de Withstraat",
                                        "locatorDesignatorNumber": 45,
                                        "postCode": "3012BK",
                                        "postName": "Rotterdam",
                                        "fullAddress": "Witte de Withstraat 45, 3012BK Rotterdam",
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
            "model": ActivityBulkResponse,
            "content": {
                "application/json": {
                    "example": {
                        "totalReceived": 6,
                        "succeeded": 2,
                        "failed": 4,
                        "results": [
                            {
                                "activityIndex": 0,
                                "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "OK",
                                "activity": {
                                    "activityId": "550e8400-e29b-41d4-a716-446655440000",
                                    "activityName": "Amsterdam Summer Rental",
                                    "status": "finished",
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
                                        "fullAddress": "Prinsengracht 263a-II, 1016GV Amsterdam",
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
                                    "activityId": "660f9511-f30c-52e5-b827-557766551111",
                                    "activityName": "Rotterdam Weekend Stay",
                                    "status": "cancelled",
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
                                        "fullAddress": "Witte de Withstraat 45, 3012BK Rotterdam",
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
                            {
                                "activityIndex": 4,
                                "activityId": "882b1733-h52e-74g7-d049-779988773333",
                                "status": "NOK",
                                "errors": {
                                    "detail": [
                                        {
                                            "msg": "Area with areaId '00000000-0000-0000-0000-000000000000' not found",
                                            "type": "not_found_error",
                                            "loc": ["areaId"],
                                        }
                                    ]
                                },
                            },
                            {
                                "activityIndex": 5,
                                "activityId": "993c2844-i63f-85h8-e15a-880099884444",
                                "status": "NOK",
                                "errors": {
                                    "detail": [
                                        {
                                            "msg": "Value error, numberOfGuests (3) must equal the number of elements in countryOfGuests (2)",
                                            "type": "value_error",
                                            "loc": [],
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
            "model": ActivityBulkResponse,
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
                                            "msg": "Area with areaId '00000000-0000-0000-0000-000000000000' not found",
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
                                            "msg": "Area with areaId '00000000-0000-0000-0000-000000000000' not found",
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
                                "status": "finished",
                                "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
                                "url": "http://example.com/amsterdam-myhouse-1",
                                "address": {
                                    "thoroughfare": "Prinsengracht",
                                    "locatorDesignatorNumber": 263,
                                    "locatorDesignatorLetter": "a",
                                    "locatorDesignatorAddition": "II",
                                    "postCode": "1016GV",
                                    "postName": "Amsterdam",
                                    "fullAddress": "Prinsengracht 263a-II, 1016GV Amsterdam",
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
                                "status": "cancelled",
                                "areaId": "904ee15d-70a6-4e69-a704-6018646803a8",
                                "url": "http://example.com/rotterdam-apartment-2",
                                "address": {
                                    "thoroughfare": "Witte de Withstraat",
                                    "locatorDesignatorNumber": 45,
                                    "postCode": "3012BK",
                                    "postName": "Rotterdam",
                                    "fullAddress": "Witte de Withstraat 45, 3012BK Rotterdam",
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
                                "areaId": "bb22937c-fa9b-4ce6-b3d9-6e2ac49f621c",
                                "url": "http://example.com/utrecht-studio-3",
                                "address": {
                                    "thoroughfare": "Oudegracht",
                                    "locatorDesignatorNumber": 100,
                                    "postCode": "3511AX",
                                    "postName": "Utrecht",
                                    "fullAddress": "Oudegracht 100, 3511AX Utrecht",
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
                                "areaId": "6d1da866-c6c4-48f7-a15a-a7aae27c73f8",
                                "url": "http://example.com/denhaag-apartment-4",
                                "address": {
                                    "thoroughfare": "Turfmarkt",
                                    "locatorDesignatorNumber": 147,
                                    "postCode": "2500EA",
                                    "postName": "Den Haag",
                                    "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
                                },
                                "registrationNumber": "REG0004",
                                "numberOfGuests": 1,
                                "countryOfGuests": ["ESP"],
                            },
                            {
                                "activityId": "882b1733-h52e-74g7-d049-779988773333",
                                "activityName": "Groningen Loft",
                                "areaId": "00000000-0000-0000-0000-000000000000",
                                "url": "http://example.com/groningen-loft-5",
                                "address": {
                                    "thoroughfare": "Herestraat",
                                    "locatorDesignatorNumber": 20,
                                    "postCode": "9711LA",
                                    "postName": "Groningen",
                                    "fullAddress": "Herestraat 20, 9711LA Groningen",
                                },
                                "registrationNumber": "REG0005",
                                "numberOfGuests": 2,
                                "countryOfGuests": ["ITA", "ITA"],
                                "temporal": {
                                    "startDatetime": "2025-09-01T14:00:00Z",
                                    "endDatetime": "2025-09-03T10:00:00Z",
                                },
                            },
                            {
                                "activityId": "993c2844-i63f-85h8-e15a-880099884444",
                                "activityName": "Eindhoven Studio",
                                "areaId": "959a7439-7cad-4009-96ec-353b44723db9",
                                "url": "http://example.com/eindhoven-studio-6",
                                "address": {
                                    "thoroughfare": "Stratumseind",
                                    "locatorDesignatorNumber": 12,
                                    "postCode": "5611EP",
                                    "postName": "Eindhoven",
                                    "fullAddress": "Stratumseind 12, 5611EP Eindhoven",
                                },
                                "registrationNumber": "REG0006",
                                "numberOfGuests": 3,
                                "countryOfGuests": ["NLD", "NLD"],
                                "temporal": {
                                    "startDatetime": "2025-10-01T14:00:00Z",
                                    "endDatetime": "2025-10-03T10:00:00Z",
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
    request: ActivityBulkRequest,
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
    # `activities` is typed as `list[ActivityRequest]` for the OpenAPI contract
    # but uses `SkipValidation`, so at runtime items are raw dicts — cast to
    # match the service signature.
    result = await activity_bulk_service.create_activities_bulk(
        session=session,
        activities_raw=cast("list[dict[str, Any]]", request.activities),
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
