"""CA v2 areas list endpoint (limit defaults to 1000)."""

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import ClientDependency, RequireRoles
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.api.domains.ca.routers.areas_docs import (
    OWN_AREAS_DESCRIPTION_V2,
    OWN_AREAS_RESPONSES,
    OWN_AREAS_SUMMARY,
)
from app.db.config import get_async_db_read_only
from app.schemas.area import AreaListResponse, AreaResponse
from app.services import area as area_service

router = APIRouter(tags=["ca"])


@router.get(
    "/areas",
    summary=OWN_AREAS_SUMMARY,
    description=OWN_AREAS_DESCRIPTION_V2,
    operation_id="getOwnAreasV2",
    response_model=AreaListResponse,
    status_code=status.HTTP_200_OK,
    responses=OWN_AREAS_RESPONSES,
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_own_areas(
    client: ClientDependency,
    pagination: LimitedPaginationDependency,
    session: AsyncSession = Depends(get_async_db_read_only),
) -> Response:
    """
    Get areas for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    """
    area_objects = await area_service.get_areas_by_client_id(
        session,
        client_id=client.id,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    areas = [AreaResponse.model_validate(area_obj) for area_obj in area_objects]

    response = AreaListResponse(areas=areas)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response.model_dump(by_alias=True, mode="json"),
    )
