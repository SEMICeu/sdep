"""OpenAPI text and examples for the CA areas list endpoint, shared by v1 and v2."""

from typing import Any

from app.schemas.area import AreaListResponse
from app.schemas.error import ErrorResponse

OWN_AREAS_SUMMARY = "Get areas for the currently authenticated competent authority"

OWN_AREAS_ITEM_DESCRIPTION = """**Scoping:**
- Only returns areas belonging to the currently authenticated competent authority (based on JWT client_id)

**Each area contains:**
- `areaId`: Functional ID identifying this area
- `areaName`: Display name (optional) of the area
- `regulation`: Regulation type: 'listing', 'activity', or 'all'
- `filename`: Name of the area shapefile (e.g., 'area.zip')
- `competentAuthorityId`: Functional ID of the competent authority that owns the area
- `competentAuthorityName`: Display name (optional) of the competent authority
- `createdAt`: Timestamp when this area version was created (UTC)
"""

OWN_AREAS_DESCRIPTION_V1 = (
    "Get all areas owned by the currently authenticated competent authority. By default, returns all areas (unlimited). Use optional pagination parameters to limit results.\n\n"
    + OWN_AREAS_ITEM_DESCRIPTION
    + """
**Pagination:**
- `offset`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: unlimited)
"""
)

# CA v2: the limit defaults to the maximum, so one
# call never returns more than 1000 areas.
OWN_AREAS_DESCRIPTION_V2 = (
    "Get all areas owned by the currently authenticated competent authority, maximum 1000 per page. `limit` defaults to 1000 (the maximum); use `offset` and `limit` to page through the result set, and `GET /areas/count` for the total.\n\n"
    + OWN_AREAS_ITEM_DESCRIPTION
    + """
**Pagination:**
- `offset`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: 1000, max: 1000)
"""
)

OWN_AREAS_RESPONSES: dict[int | str, dict[str, Any]] = {
    "200": {
        "description": "List of areas owned by the authenticated competent authority",
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
