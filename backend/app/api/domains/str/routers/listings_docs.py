"""OpenAPI text and examples for the STR listing endpoints (random checks)."""

from typing import Any

from app.api.common.listing_examples import (
    EXAMPLE_LISTING_ACKNOWLEDGED,
    EXAMPLE_LISTING_FLAGGED,
    EXAMPLE_LISTING_PENDING,
    FILTERS_NOTE,
    LISTING_FIELDS_DESCRIPTION,
    PAGINATION_NOTE,
)
from app.schemas.error import ErrorResponse
from app.schemas.listing_bulk import (
    ListingAcknowledgementBulkResponse,
    ListingBulkResponse,
)

# ── GET /listings ────────────────────────────────────────────────────────

LISTINGS_SUMMARY = "Get the flagged listings of the currently authenticated platform"

LISTINGS_DESCRIPTION = (
    "Get the current listings of the currently authenticated platform that were flagged by the screening and not yet acknowledged (fixed scope: `status` is `flagged`, `acknowledgedAt` is null). "
    "Acknowledge them with `POST /listing-acknowledgements/bulk`. "
    f"{PAGINATION_NOTE} {FILTERS_NOTE}\n\n{LISTING_FIELDS_DESCRIPTION}"
)

COUNT_LISTINGS_SUMMARY = "Get the count of flagged listings of the currently authenticated platform (optional, to support pagination)"

COUNT_LISTINGS_DESCRIPTION = f"Get the count of the current flagged listings of the currently authenticated platform (optional, to support pagination). {FILTERS_NOTE}"

# ── POST /listings/bulk ──────────────────────────────────────────────────

BULK_SUMMARY = (
    "Submit randomly selected listings in bulk for the currently authenticated platform"
)

BULK_DESCRIPTION = """Submit 1-1000 randomly selected listings for screening (random checks, see the functional design). Every submitted listing starts `pending`; the listing screening authority sets it to `clear` or `flagged`, and the platform acknowledges flagged listings via `POST /listing-acknowledgements/bulk`.

**ID Pattern:**
- `listingId`: provided by the platform as business identifier (optional), otherwise generated as UUIDv4 (RFC 9562)

**Versioning:**
- Same `listingId` can be resubmitted while the listing is `pending` → creates a new `pending` version (a correction)
- A listing that is already screened (`clear`, `flagged`, `acknowledged`) cannot be corrected: such items are marked NOK with `conflict_error`. Submit it under a new `listingId` instead (a new random check)
- Unique constraint: (`listingId`, `createdAt`, current authenticated platform)

**Validation flow (4 steps):**

1. **Syntax and semantical validation** - each item is validated individually.
   Failed items are marked NOK with the error reason; valid items continue.
2. **Referential Integrity Check** - area IDs are verified. Items with unknown `areaId` are marked NOK (`not_found_error`).
   Listings are rejected for areas that are regulated for activity only (`regulation` is `activity`): such items are marked NOK with `regulation_error`.
3. **Versioning and Bulk Insert** - the current version is locked and checked (`pending`), marked ended, and all remaining valid items are inserted as new versions in a single multi-row INSERT.
4. **Feedback** - per-item OK/NOK response preserving original order.

**Intra-batch duplicates (last-wins):**
When the same `listingId` appears multiple times in a single batch, only the last
occurrence is processed. Earlier occurrences receive NOK.

**The request contains:**
- `listings`: Array of listing objects to process (1-1000 items per batch)

**Each listing item in the request contains:**
- `listingId`: Functional ID identifying the listing (alphanumeric with hyphens `^[A-Za-z0-9\\-]+$`, max 64 chars, optionally supplied, auto-generated as UUIDv4 RFC 9562 if not supplied)
- `listingName`: Display name of the listing (optional, max 64 chars)
- `areaId`: Functional ID referencing the area where the listing is posted
- `url`: URL referencing the listing online (max 2048 chars)
- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)
- `declaredAsShortTermRental`: Host self-declaration (`true` or `false`)
- `registrationNumber`: Registration number shown on the listing (optional, max 32 chars)

**The response contains:**
- `totalReceived`: Total number of items received in the request
- `succeeded`: Number of items successfully created (status OK)
- `failed`: Number of items that failed validation or processing (status NOK)
- `results`: Per-item results preserving the original request order

**Each results item contains:**
- `listingIndex`: Zero-based index of this item in the original request list
- `listingId`: Listing functional ID provided by the client in the request
- `status`: Processing result - `OK` (created successfully) or `NOK` (failed validation or processing)
- `listing`: The listing as it now is (present for OK items, omitted for NOK items), see `GET /listings` for its fields
- `errors`: Structured error details (present for NOK items, omitted for OK items)

**Response HTTP status:**
- 201: all items created successfully
- 200: partial success (some OK, some NOK)
- 401: missing or invalid token
- 403: insufficient permissions
- 422: all items failed
"""

_REQUEST_LISTING: dict[str, Any] = {
    "listingId": "550e8400-e29b-41d4-a716-446655440000",
    "listingName": "Amsterdam Canal Apartment",
    "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
    "url": "http://example.com/amsterdam-canal-apartment",
    "address": {
        "thoroughfare": "Prinsengracht",
        "locatorDesignatorNumber": 263,
        "postCode": "1016GV",
        "postName": "Amsterdam",
        "fullAddress": "Prinsengracht 263, 1016GV Amsterdam",
    },
    "declaredAsShortTermRental": True,
    "registrationNumber": "REG0001",
}

_REQUEST_LISTING_ROTTERDAM: dict[str, Any] = {
    "listingName": "Rotterdam Harbor View",
    "areaId": "974e2c23-b666-5044-a05c-9479a4c293a1",
    "url": "http://example.com/rotterdam-harbor-view",
    "address": {
        "thoroughfare": "Wilhelminakade",
        "locatorDesignatorNumber": 50,
        "postCode": "3072AP",
        "postName": "Rotterdam",
        "fullAddress": "Wilhelminakade 50, 3072AP Rotterdam",
    },
    "declaredAsShortTermRental": False,
}

_RESPONSE_LISTING_ROTTERDAM: dict[str, Any] = {
    **EXAMPLE_LISTING_PENDING,
    "listingId": "1d1a7f0c-2b4e-4a63-9c0f-7c1e5b2a9d10",
    "listingName": "Rotterdam Harbor View",
    "areaId": "974e2c23-b666-5044-a05c-9479a4c293a1",
    "areaName": "Rotterdam",
    "competentAuthorityId": "a30df3a7-7e38-534c-b9c0-7666bad077d2",
    "competentAuthorityName": "Rotterdam",
    "url": "http://example.com/rotterdam-harbor-view",
    "address": _REQUEST_LISTING_ROTTERDAM["address"],
    "declaredAsShortTermRental": False,
    "registrationNumber": None,
}

BULK_RESPONSES: dict[int | str, dict[str, Any]] = {
    "201": {
        "description": "All listings created successfully",
        "model": ListingBulkResponse,
        "content": {
            "application/json": {
                "example": {
                    "totalReceived": 2,
                    "succeeded": 2,
                    "failed": 0,
                    "results": [
                        {
                            "listingIndex": 0,
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "OK",
                            "listing": EXAMPLE_LISTING_PENDING,
                        },
                        {
                            "listingIndex": 1,
                            "listingId": None,
                            "status": "OK",
                            "listing": _RESPONSE_LISTING_ROTTERDAM,
                        },
                    ],
                }
            }
        },
    },
    "200": {
        "description": "Partial success - some listings created, some failed",
        "model": ListingBulkResponse,
        "content": {
            "application/json": {
                "example": {
                    "totalReceived": 4,
                    "succeeded": 1,
                    "failed": 3,
                    "results": [
                        {
                            "listingIndex": 0,
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "OK",
                            "listing": EXAMPLE_LISTING_PENDING,
                        },
                        {
                            "listingIndex": 1,
                            "listingId": None,
                            "status": "NOK",
                            "errors": {
                                "detail": [
                                    {
                                        "msg": "Field required",
                                        "type": "missing",
                                        "loc": ["declaredAsShortTermRental"],
                                    }
                                ]
                            },
                        },
                        {
                            "listingIndex": 2,
                            "listingId": "882b1733-h52e-74g7-d049-779988773333",
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
                            "listingIndex": 3,
                            "listingId": "993c2844-i63f-85h8-e15a-880099884444",
                            "status": "NOK",
                            "errors": {
                                "detail": [
                                    {
                                        "msg": "Listing '993c2844-i63f-85h8-e15a-880099884444' is already screened (status 'flagged')",
                                        "type": "conflict_error",
                                        "loc": ["listingId"],
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
        "model": ListingBulkResponse,
        "description": "All listings failed validation",
        "content": {
            "application/json": {
                "example": {
                    "totalReceived": 1,
                    "succeeded": 0,
                    "failed": 1,
                    "results": [
                        {
                            "listingIndex": 0,
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
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
                        }
                    ],
                }
            }
        },
    },
}

BULK_OPENAPI_EXTRA: dict[str, Any] = {
    "requestBody": {
        "content": {
            "application/json": {
                "example": {
                    "listings": [
                        _REQUEST_LISTING,
                        _REQUEST_LISTING_ROTTERDAM,
                        {
                            "listingId": "882b1733-h52e-74g7-d049-779988773333",
                            "listingName": "Groningen Loft",
                            "areaId": "00000000-0000-0000-0000-000000000000",
                            "url": "http://example.com/groningen-loft",
                            "address": {
                                "thoroughfare": "Herestraat",
                                "locatorDesignatorNumber": 20,
                                "postCode": "9711LA",
                                "postName": "Groningen",
                                "fullAddress": "Herestraat 20, 9711LA Groningen",
                            },
                            "declaredAsShortTermRental": True,
                        },
                    ]
                }
            }
        }
    }
}

# ── POST /listing-acknowledgements/bulk ──────────────────────────────────

ACK_SUMMARY = (
    "Acknowledge flagged listings in bulk for the currently authenticated platform"
)

ACK_DESCRIPTION = """Acknowledge 1-1000 flagged listings (= random check performed). Each acknowledged listing becomes a new `acknowledged` version; its flags are retained. The acknowledgement carries no further data.

**Concurrency:**
- `createdAt` is the `createdAt` of the flagged version, as returned by `GET /listings`
- When that version is no longer current (for example, the listing was re-screened), the item is marked NOK with `conflict_error` and `loc` `["createdAt"]`; the listing then reappears in `GET /listings` with its new version
- A retried acknowledgement fails the same way: treat it as "already acknowledged"

**Validation flow (4 steps):**

1. **Syntax and semantical validation** - each item is validated individually.
2. **Referential Integrity Check** - the listing must exist for the currently authenticated platform (`not_found_error`).
3. **Versioning and Bulk Insert** - the current version is locked and checked (`createdAt` current, status `flagged`), marked ended, and the `acknowledged` versions are inserted in a single multi-row INSERT.
4. **Feedback** - per-item OK/NOK response preserving original order.

**Intra-batch duplicates (last-wins):**
When the same `listingId` appears multiple times in a single batch, only the last
occurrence is processed. Earlier occurrences receive NOK.

**The request contains:**
- `acknowledgements`: Array of acknowledgements to process (1-1000 items per batch)

**Each acknowledgement item in the request contains:**
- `listingId`: Functional ID of the flagged listing
- `createdAt`: `createdAt` of the flagged listing version (UTC)

**The response contains:**
- `totalReceived`, `succeeded`, `failed`: Summary counts
- `results`: Per-item results preserving the original request order (`listingIndex`, `listingId`, `status`, `listing` for OK items, `errors` for NOK items)

**Response HTTP status:**
- 201: all items acknowledged
- 200: partial success (some OK, some NOK)
- 401: missing or invalid token
- 403: insufficient permissions
- 422: all items failed
"""

ACK_RESPONSES: dict[int | str, dict[str, Any]] = {
    "201": {
        "description": "All listings acknowledged",
        "model": ListingAcknowledgementBulkResponse,
        "content": {
            "application/json": {
                "example": {
                    "totalReceived": 1,
                    "succeeded": 1,
                    "failed": 0,
                    "results": [
                        {
                            "listingIndex": 0,
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "OK",
                            "listing": EXAMPLE_LISTING_ACKNOWLEDGED,
                        }
                    ],
                }
            }
        },
    },
    "200": {
        "description": "Partial success - some listings acknowledged, some failed",
        "model": ListingAcknowledgementBulkResponse,
        "content": {
            "application/json": {
                "example": {
                    "totalReceived": 3,
                    "succeeded": 1,
                    "failed": 2,
                    "results": [
                        {
                            "listingIndex": 0,
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "OK",
                            "listing": EXAMPLE_LISTING_ACKNOWLEDGED,
                        },
                        {
                            "listingIndex": 1,
                            "listingId": "abc-123",
                            "status": "NOK",
                            "errors": {
                                "detail": [
                                    {
                                        "msg": "Listing 'abc-123' version '2026-09-07T08:00:00Z' is no longer current",
                                        "type": "conflict_error",
                                        "loc": ["createdAt"],
                                    }
                                ]
                            },
                        },
                        {
                            "listingIndex": 2,
                            "listingId": "unknown-id",
                            "status": "NOK",
                            "errors": {
                                "detail": [
                                    {
                                        "msg": "Listing 'unknown-id' not found",
                                        "type": "not_found_error",
                                        "loc": ["listingId"],
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
        "model": ListingAcknowledgementBulkResponse,
        "description": "All acknowledgements failed",
        "content": {
            "application/json": {
                "example": {
                    "totalReceived": 1,
                    "succeeded": 0,
                    "failed": 1,
                    "results": [
                        {
                            "listingIndex": 0,
                            "listingId": "abc-123",
                            "status": "NOK",
                            "errors": {
                                "detail": [
                                    {
                                        "msg": "Listing 'abc-123' version '2026-09-07T08:00:00Z' is no longer current",
                                        "type": "conflict_error",
                                        "loc": ["createdAt"],
                                    }
                                ]
                            },
                        }
                    ],
                }
            }
        },
    },
}

ACK_OPENAPI_EXTRA: dict[str, Any] = {
    "requestBody": {
        "content": {
            "application/json": {
                "example": {
                    "acknowledgements": [
                        {
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
                            "createdAt": EXAMPLE_LISTING_FLAGGED["createdAt"],
                        }
                    ]
                }
            }
        }
    }
}
