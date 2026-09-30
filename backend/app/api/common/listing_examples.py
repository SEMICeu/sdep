"""Shared OpenAPI response examples for listing read endpoints."""

from typing import Any

from app.schemas.error import ErrorResponse

# One example listing per lifecycle state, so every audience can point at the
# state it reads. Area and competent authority IDs come from the seed data.
EXAMPLE_LISTING_PENDING: dict[str, Any] = {
    "listingId": "550e8400-e29b-41d4-a716-446655440000",
    "listingName": "Amsterdam Canal Apartment",
    "status": "pending",
    "flags": [],
    "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
    "areaName": "Amsterdam",
    "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
    "competentAuthorityName": "Amsterdam (inclusief Weesp)",
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
    "submittedAt": "2026-09-07T08:00:00Z",
    "screenedAt": None,
    "acknowledgedAt": None,
    "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
    "platformName": "Test STR 01",
    "createdAt": "2026-09-07T08:00:00Z",
}

EXAMPLE_LISTING_FLAGGED: dict[str, Any] = {
    **EXAMPLE_LISTING_PENDING,
    "status": "flagged",
    "flags": ["UNK"],
    "screenedAt": "2026-09-08T06:00:00Z",
    "createdAt": "2026-09-08T06:00:00Z",
}

EXAMPLE_LISTING_ACKNOWLEDGED: dict[str, Any] = {
    **EXAMPLE_LISTING_FLAGGED,
    "status": "acknowledged",
    "acknowledgedAt": "2026-09-09T10:00:00Z",
    "createdAt": "2026-09-09T10:00:00Z",
}

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
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
}


def listing_example_response(
    *listings: dict[str, Any],
) -> dict[int | str, dict[str, Any]]:
    """`responses` dict for a GET /listings endpoint, with the given example items."""
    return {
        "200": {
            "content": {"application/json": {"example": {"listings": list(listings)}}}
        },
        **_ERROR_RESPONSES,
    }


COUNT_LISTING_RESPONSES: dict[int | str, dict[str, Any]] = {
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
}

__all__ = [
    "COUNT_LISTING_RESPONSES",
    "EXAMPLE_LISTING_ACKNOWLEDGED",
    "EXAMPLE_LISTING_FLAGGED",
    "EXAMPLE_LISTING_PENDING",
    "FILTERS_NOTE",
    "LISTING_FIELDS_DESCRIPTION",
    "PAGINATION_NOTE",
    "listing_example_response",
]

LISTING_FIELDS_DESCRIPTION = (
    "**Each listing contains:**\n"
    "- `listingId`: Functional ID identifying this listing\n"
    "- `listingName`: Display name (optional) of the listing\n"
    "- `status`: Lifecycle status: `pending`, `clear`, `flagged` or `acknowledged`\n"
    "- `flags`: Flag codes raised by the screening (`ABS`, `UNK`, `EXP`, `MIS`, `NPR`, `UNX`, `UDS`); empty until screened\n"
    "- `areaId`: Functional ID referencing the area where the listing is posted\n"
    "- `areaName`: Display name (optional) of the area\n"
    "- `competentAuthorityId`: Functional ID referencing the competent authority that owns the area\n"
    "- `competentAuthorityName`: Display name (optional) of the competent authority\n"
    "- `url`: URL referencing the listing online\n"
    "- `address`: Address composite (`thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)\n"
    "- `declaredAsShortTermRental`: Host self-declaration\n"
    "- `registrationNumber`: Registration number shown on the listing (optional)\n"
    "- `submittedAt`: Timestamp of the platform's submission (UTC)\n"
    "- `screenedAt`: Timestamp of the screening (UTC, null until screened)\n"
    "- `acknowledgedAt`: Timestamp of the acknowledgement (UTC, null until acknowledged)\n"
    "- `platformId`: Functional ID referencing the platform that submitted the listing\n"
    "- `platformName`: Display name (optional) of the platform\n"
    "- `createdAt`: Timestamp when this listing version was created (UTC); the version token for screening and acknowledgement"
)

FILTERS_NOTE = "Optional filters use AND semantics: every provided filter narrows the result set. The `createdAtFrom` and `createdAtTo` form an inclusive `createdAt` range; the other filters are exact-match, except `flags` which matches any of the given codes."

PAGINATION_NOTE = "Returns at most 1000 listings per request (the default and maximum `limit`). Use the `offset` and `limit` pagination parameters to page through results."
