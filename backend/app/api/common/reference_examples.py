"""OpenAPI text and examples for the platform and competent authority reads.

Used by the router factories in reference_routers.py. The area texts live in
area_examples.py, shared with STR.
"""

from typing import Any

from app.schemas.competent_authority import CompetentAuthorityListResponse
from app.schemas.error import ErrorResponse
from app.schemas.platform import PlatformListResponse

LIST_NOTE = "Returns at most 1000 records per request (the default and maximum `limit`). Use the `offset` and `limit` pagination parameters to page through results, and the `/count` endpoint for the total."

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
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


# ── Platforms ────────────────────────────────────────────────────────────

EXAMPLE_PLATFORM: dict[str, Any] = {
    "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
    "platformName": "Test STR 01",
    "createdAt": "2025-01-01T00:00:00Z",
}

PLATFORM_ITEM_DESCRIPTION = (
    "**Each platform contains:**\n"
    "- `platformId`: Functional ID identifying this platform\n"
    "- `platformName`: Display name (optional) of the platform\n"
    "- `createdAt`: Timestamp when this platform version was created (UTC)"
)

PLATFORMS_SUMMARY = "Get all platforms"
PLATFORMS_DESCRIPTION = (
    f"Get all current platforms. {LIST_NOTE} Use `platformId` as the `platformId` filter of the activity and listing reads.\n\n"
    + PLATFORM_ITEM_DESCRIPTION
)
COUNT_PLATFORMS_SUMMARY = "Get platforms count (optional, to support pagination)"

PLATFORMS_RESPONSES: dict[int | str, dict[str, Any]] = {
    "200": {
        "description": "List of platforms",
        "model": PlatformListResponse,
        "content": {"application/json": {"example": {"platforms": [EXAMPLE_PLATFORM]}}},
    },
    **ERROR_RESPONSES,
}

# ── Competent authorities ────────────────────────────────────────────────

EXAMPLE_COMPETENT_AUTHORITY: dict[str, Any] = {
    "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
    "competentAuthorityName": "Amsterdam (inclusief Weesp)",
    "createdAt": "2025-01-01T00:00:00Z",
}

COMPETENT_AUTHORITY_ITEM_DESCRIPTION = (
    "**Each competent authority contains:**\n"
    "- `competentAuthorityId`: Functional ID identifying this competent authority\n"
    "- `competentAuthorityName`: Display name (optional) of the competent authority\n"
    "- `createdAt`: Timestamp when this competent authority version was created (UTC)"
)

COMPETENT_AUTHORITIES_SUMMARY = "Get all competent authorities"
COMPETENT_AUTHORITIES_DESCRIPTION = (
    f"Get all current competent authorities. {LIST_NOTE} Use `competentAuthorityId` as the `competentAuthorityId` filter of the activity and listing reads.\n\n"
    + COMPETENT_AUTHORITY_ITEM_DESCRIPTION
)
COUNT_COMPETENT_AUTHORITIES_SUMMARY = (
    "Get competent authorities count (optional, to support pagination)"
)

COMPETENT_AUTHORITIES_RESPONSES: dict[int | str, dict[str, Any]] = {
    "200": {
        "description": "List of competent authorities",
        "model": CompetentAuthorityListResponse,
        "content": {
            "application/json": {
                "example": {"competentAuthorities": [EXAMPLE_COMPETENT_AUTHORITY]}
            }
        },
    },
    **ERROR_RESPONSES,
}
