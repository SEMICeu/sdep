"""OpenAPI text and examples for the STR areas list endpoint, shared by v1 and v2."""

from typing import Any

from app.schemas.area import AreaListResponse
from app.schemas.error import ErrorResponse

AREAS_SUMMARY = "Get all areas"

AREAS_ITEM_DESCRIPTION = (
    "**Each area contains:**\n"
    "- `areaId`: Functional ID identifying this area\n"
    "- `areaName`: Display name (optional) of the area\n"
    "- `regulation`: Regulation type of the area - 'listing', 'activity', or 'all'\n"
    "- `filename`: Name of the area shapefile (e.g., 'area.zip')\n"
    "- `competentAuthorityId`: Functional ID referencing the competent authority that owns the area\n"
    "- `competentAuthorityName`: Display name (optional) of the competent authority\n"
    "- `createdAt`: Timestamp when this area version was created (UTC)"
)

AREAS_DESCRIPTION_V1 = (
    "Get all areas. By default, returns all areas (unlimited). Use optional pagination parameters to limit results.\n\n"
    + AREAS_ITEM_DESCRIPTION
)

# STR v2: the limit defaults to the maximum, so one call never returns
# more than 1000 areas. Clients page with offset/limit and use /areas/count.
AREAS_DESCRIPTION_V2 = (
    "Get all areas, maximum 1000 per page. `limit` defaults to 1000 (the maximum); use `offset` and `limit` to page through the result set, and `GET /areas/count` for the total.\n\n"
    + AREAS_ITEM_DESCRIPTION
)

AREAS_RESPONSES: dict[int | str, dict[str, Any]] = {
    "200": {
        "description": "List of areas",
        "model": AreaListResponse,
        "content": {
            "application/json": {
                "example": {
                    "areas": [
                        {
                            "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
                            "areaName": "Amsterdam",
                            "regulation": "all",
                            "filename": "Amsterdam.zip",
                            "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
                            "competentAuthorityName": "Amsterdam (inclusief Weesp)",
                            "createdAt": "2025-01-01T00:00:00Z",
                        },
                        {
                            "areaId": "974e2c23-b666-5044-a05c-9479a4c293a1",
                            "areaName": "Rotterdam",
                            "regulation": "all",
                            "filename": "Rotterdam.zip",
                            "competentAuthorityId": "a30df3a7-7e38-534c-b9c0-7666bad077d2",
                            "competentAuthorityName": "Rotterdam",
                            "createdAt": "2025-01-01T00:00:00Z",
                        },
                    ],
                }
            }
        },
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
}
