"""STR v2 areas list endpoint (limit defaults to 1000)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import RequireRoles
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.api.domains.str.routers.areas_docs import (
    AREAS_DESCRIPTION_V2,
    AREAS_RESPONSES,
    AREAS_SUMMARY,
)
from app.db.config import get_async_db_read_only
from app.schemas.area import AreaListResponse, AreaResponse
from app.services import area

router = APIRouter(tags=["str"])


@router.get(
    "/areas",
    response_model=AreaListResponse,
    status_code=status.HTTP_200_OK,
    summary=AREAS_SUMMARY,
    description=AREAS_DESCRIPTION_V2,
    operation_id="getAreasV2",
    responses=AREAS_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.STR, Role.READ))],
)
async def get_areas(
    pagination: LimitedPaginationDependency,
    session: AsyncSession = Depends(get_async_db_read_only),
) -> AreaListResponse:
    """
    Get areas in context of the current SDEP/member state.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_read" roles in realm_access

    Pagination parameters:
    - offset: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 1000, max: 1000)
    """
    area_objects = await area.get_areas(
        session,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    area_responses = [
        AreaResponse.model_validate(area_obj) for area_obj in area_objects
    ]

    return AreaListResponse(areas=area_responses)
