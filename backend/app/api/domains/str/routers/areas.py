"""STR areas endpoints shared by every version: count and shapefile download."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import RequireRoles
from app.api.common.filename import (
    content_disposition_header,
    sanitize_download_filename,
)
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.area import AreaCountResponse
from app.schemas.error import ErrorResponse
from app.services import area

router = APIRouter(tags=["str"])


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
