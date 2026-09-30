"""OpenAPI text and examples for the listing screening authority (LSA) endpoints."""

from typing import Any

from app.api.common.listing_examples import (
    EXAMPLE_LISTING_FLAGGED,
    EXAMPLE_LISTING_PENDING,
    FILTERS_NOTE,
    LISTING_FIELDS_DESCRIPTION,
    PAGINATION_NOTE,
)
from app.schemas.error import ErrorResponse
from app.schemas.listing_bulk import ListingScreeningBulkResponse

# ── GET /listings ────────────────────────────────────────────────────────

LISTINGS_SUMMARY = "Get the submitted listings awaiting screening, across all platforms"

LISTINGS_DESCRIPTION = (
    "Get the current listings that platforms submitted for screening and that are not yet screened (fixed scope: `status` is `pending`, `flags` empty, `screenedAt` null), across all platforms. "
    "Submit the screening results with `POST /listing-screenings/bulk`. "
    f"{PAGINATION_NOTE} {FILTERS_NOTE} Use `areaId`, `platformId` and `competentAuthorityId` to group the work by area, platform and/or competent authority.\n\n{LISTING_FIELDS_DESCRIPTION}"
)

COUNT_LISTINGS_SUMMARY = (
    "Get the count of listings awaiting screening (optional, to support pagination)"
)

COUNT_LISTINGS_DESCRIPTION = f"Get the count of the current listings awaiting screening, across all platforms (optional, to support pagination). {FILTERS_NOTE}"

# ── POST /listing-screenings/bulk ────────────────────────────────────────

SCREENING_SUMMARY = "Submit screening results in bulk"

SCREENING_DESCRIPTION = """Submit 1-1000 screening results. Each screened listing becomes a new version: `clear` when `flags` is empty, `flagged` otherwise. Flagged listings appear in the platform's `GET /listings` for acknowledgement.

**Flag codes:** `ABS` (absent registration number), `UNK` (unknown registration number), `EXP` (expired registration number), `MIS` (mismatched address), `NPR` (not a private residence), `UNX` (unexpected registration number), `UDS` (undeclared short-term rental). See the functional design for the decision table.

**Correction:** a `clear` or `flagged` listing may be re-screened (new version, state follows the new flags). An `acknowledged` listing is final: such items are marked NOK with `conflict_error`.

**Concurrency:**
- `platformId` and `listingId` identify the listing (a `listingId` is only unique within a platform)
- `createdAt` is the `createdAt` of the version that was screened, as returned by `GET /listings`
- When that version is no longer current (for example, the platform corrected the listing), the item is marked NOK with `conflict_error` and `loc` `["createdAt"]`; the corrected listing reappears in `GET /listings` with its new data

**Validation flow (4 steps):**

1. **Syntax and semantical validation** - each item is validated individually (`platformId`, `listingId`, UTC `createdAt`, known flag codes).
2. **Referential Integrity Check** - the platform and the listing must exist (`not_found_error`).
3. **Versioning and Bulk Insert** - the current version is locked and checked (`createdAt` current, status not `acknowledged`), marked ended, and the screened versions are inserted in a single multi-row INSERT.
4. **Feedback** - per-item OK/NOK response preserving original order.

**Intra-batch duplicates (last-wins):**
When the same (`platformId`, `listingId`) appears multiple times in a single batch, only the last
occurrence is processed. Earlier occurrences receive NOK.

**The request contains:**
- `screenings`: Array of screening results to process (1-1000 items per batch)

**Each screening item in the request contains:**
- `platformId`: Functional ID of the platform that submitted the listing
- `listingId`: Functional ID of the screened listing
- `createdAt`: `createdAt` of the screened listing version (UTC)
- `flags`: Zero or more distinct flag codes

**The response contains:**
- `totalReceived`, `succeeded`, `failed`: Summary counts
- `results`: Per-item results preserving the original request order (`listingIndex`, `listingId`, `status`, `listing` for OK items, `errors` for NOK items)

**Response HTTP status:**
- 201: all items screened
- 200: partial success (some OK, some NOK)
- 401: missing or invalid token
- 403: insufficient permissions
- 422: all items failed
"""

_EXAMPLE_CLEAR: dict[str, Any] = {
    **EXAMPLE_LISTING_PENDING,
    "listingId": "1d1a7f0c-2b4e-4a63-9c0f-7c1e5b2a9d10",
    "status": "clear",
    "screenedAt": "2026-09-08T06:00:00Z",
    "createdAt": "2026-09-08T06:00:00Z",
}

SCREENING_RESPONSES: dict[int | str, dict[str, Any]] = {
    "201": {
        "description": "All screening results processed",
        "model": ListingScreeningBulkResponse,
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
                            "listing": EXAMPLE_LISTING_FLAGGED,
                        },
                        {
                            "listingIndex": 1,
                            "listingId": "1d1a7f0c-2b4e-4a63-9c0f-7c1e5b2a9d10",
                            "status": "OK",
                            "listing": _EXAMPLE_CLEAR,
                        },
                    ],
                }
            }
        },
    },
    "200": {
        "description": "Partial success - some screening results processed, some failed",
        "model": ListingScreeningBulkResponse,
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
                            "listing": EXAMPLE_LISTING_FLAGGED,
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
                            "listingId": "def-456",
                            "status": "NOK",
                            "errors": {
                                "detail": [
                                    {
                                        "msg": "Input should be 'ABS', 'UNK', 'EXP', 'MIS', 'NPR', 'UNX' or 'UDS'",
                                        "type": "enum",
                                        "loc": ["flags", "0"],
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
        "model": ListingScreeningBulkResponse,
        "description": "All screening results failed",
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
                                        "msg": "Platform with platformId 'unknown-platform' not found",
                                        "type": "not_found_error",
                                        "loc": ["platformId"],
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

SCREENING_OPENAPI_EXTRA: dict[str, Any] = {
    "requestBody": {
        "content": {
            "application/json": {
                "example": {
                    "screenings": [
                        {
                            "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
                            "listingId": "550e8400-e29b-41d4-a716-446655440000",
                            "createdAt": EXAMPLE_LISTING_PENDING["createdAt"],
                            "flags": ["UNK"],
                        },
                        {
                            "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
                            "listingId": "1d1a7f0c-2b4e-4a63-9c0f-7c1e5b2a9d10",
                            "createdAt": EXAMPLE_LISTING_PENDING["createdAt"],
                            "flags": [],
                        },
                    ]
                }
            }
        }
    }
}
