"""STR areas endpoints shared by every version: count and shapefile download."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.area_download import area_zip_response
from app.api.common.auth_dependencies import RequireRoles
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

    return area_zip_response(area_data, areaId)
