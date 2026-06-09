"""Areas endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import RequireRoles
from app.api.common.filename import (
    content_disposition_header,
    sanitize_download_filename,
)
from app.api.common.pagination import PaginationDependency
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.area import (
    AreaCountResponse,
    AreaListResponse,
    AreaResponse,
)
from app.schemas.error import ErrorResponse
from app.services import area

router = APIRouter(tags=["str"])


@router.get(
    "/areas",
    response_model=AreaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all areas",
    description="Get all areas. By default, returns all areas (unlimited). Use optional pagination parameters to limit results.\n\n"
    "**Each area contains:**\n"
    "- `areaId`: Functional ID identifying this area\n"
    "- `areaName`: Display name (optional) of the area\n"
    "- `regulation`: Regulation type of the area - 'listing', 'activity', or 'all'\n"
    "- `filename`: Name of the area shapefile (e.g., 'area.zip')\n"
    "- `competentAuthorityId`: Functional ID referencing the competent authority that owns the area\n"
    "- `competentAuthorityName`: Display name (optional) of the competent authority\n"
    "- `createdAt`: Timestamp when this area version was created (UTC)",
    operation_id="getAreas",
    responses={
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
    },
    dependencies=[Depends(RequireRoles(Role.STR, Role.READ))],
)
async def get_areas(
    pagination: PaginationDependency,
    session: AsyncSession = Depends(get_async_db_read_only),
) -> AreaListResponse:
    """
    Get areas in context of the current SDEP/member state.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access

    Pagination parameters:
    - offset: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: no limit, max: 1000)
    """
    # Call business service
    area_objects = await area.get_areas(
        session,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    area_responses = [
        AreaResponse.model_validate(area_obj) for area_obj in area_objects
    ]

    return AreaListResponse(areas=area_responses)


@router.get(
    "/areas/count",
    response_model=AreaCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get areas count (optional, to support pagination)",
    description="Get areas count (optional, to support pagination).",
    operation_id="countAreas",
    responses={
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
    },
    dependencies=[Depends(RequireRoles(Role.STR, Role.READ))],
)
async def count_areas(
    session: AsyncSession = Depends(get_async_db_read_only),
) -> AreaCountResponse:
    """
    Count all areas in context of the current SDEP/member state.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access

    Returns:
    - count: Total number of areas
    """
    # Call business service
    total_count = await area.count_areas(session)

    return AreaCountResponse(count=total_count)


@router.get(
    "/areas/{areaId}",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get area (shapefile)",
    description="Get area (shapefile) based on functional ID.",
    operation_id="getArea",
    responses={
        "200": {
            "content": {"application/zip": {}},
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
        "404": {
            "description": "Resource Not Found - area unavailable",
        },
    },
    dependencies=[Depends(RequireRoles(Role.STR, Role.READ))],
)
async def get_area(
    areaId: str,
    session: AsyncSession = Depends(get_async_db_read_only),
) -> Response:
    """
    Get specific area.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access

    Returns raw binary area.
    """
    # Call business service with technical area id
    area_data = await area.get_area_by_id(session, areaId)

    if area_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with areaId '{areaId}' not found",
        )

    # Return raw binary data (or empty bytes if filedata is None)
    binary_data = area_data.filedata if area_data.filedata is not None else b""
    filename = sanitize_download_filename(area_data.filename)

    return Response(
        content=binary_data,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition_header(filename)},
    )
