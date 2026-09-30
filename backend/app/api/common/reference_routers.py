"""Read-only reference data routers: platforms, competent authorities, areas.

Every audience that filters activities or listings on `platformId`,
`competentAuthorityId` or `areaId` gets the matching lookup endpoints, so each
filter value can be resolved in the same API. One factory per resource, so an
API takes only what it needs (CA v2: platforms only). Reads return current rows.
No read by ID: the list item carries every field. The area shapefile download
stays with STR and CA, see str/routers/areas.py.
"""

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import reference_examples as docs
from app.api.common.area_examples import (
    AREAS_DESCRIPTION_V2,
    AREAS_RESPONSES,
    AREAS_SUMMARY,
)
from app.api.common.auth_dependencies import RequireRoles
from app.api.common.pagination import LimitedPaginationDependency
from app.api.common.security import Role
from app.db.config import get_async_db_read_only
from app.schemas.area import AreaCountResponse, AreaListResponse, AreaResponse
from app.schemas.competent_authority import (
    CompetentAuthorityCountResponse,
    CompetentAuthorityListResponse,
    CompetentAuthorityResponse,
)
from app.schemas.platform import (
    PlatformCountResponse,
    PlatformListResponse,
    PlatformResponse,
)
from app.services import area as area_service
from app.services import competent_authority as competent_authority_service
from app.services import platform as platform_service

# Count endpoints take no query parameters, so no 400
_COUNT_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: docs.ERROR_RESPONSES[code] for code in ("401", "403")
}


def platforms_router(tag: str, audience: Role) -> APIRouter:
    """`GET /platforms`, `/platforms/count`."""
    router = APIRouter(tags=[tag])
    roles = [Depends(RequireRoles(audience, Role.READ))]

    @router.get(
        "/platforms",
        response_model=PlatformListResponse,
        status_code=status.HTTP_200_OK,
        summary=docs.PLATFORMS_SUMMARY,
        description=docs.PLATFORMS_DESCRIPTION,
        operation_id="getPlatforms",
        responses=docs.PLATFORMS_RESPONSES,
        dependencies=roles,
    )
    async def get_platforms(
        pagination: LimitedPaginationDependency,
        session: AsyncSession = Depends(get_async_db_read_only),
    ) -> PlatformListResponse:
        platforms = await platform_service.get_platforms(
            session, offset=pagination.offset, limit=pagination.limit
        )
        return PlatformListResponse(
            platforms=[PlatformResponse.model_validate(p) for p in platforms]
        )

    @router.get(
        "/platforms/count",
        response_model=PlatformCountResponse,
        status_code=status.HTTP_200_OK,
        summary=docs.COUNT_PLATFORMS_SUMMARY,
        description=docs.COUNT_PLATFORMS_SUMMARY,
        operation_id="countPlatforms",
        responses=_COUNT_RESPONSES,
        dependencies=roles,
    )
    async def count_platforms(
        session: AsyncSession = Depends(get_async_db_read_only),
    ) -> PlatformCountResponse:
        return PlatformCountResponse(
            count=await platform_service.count_platforms(session)
        )

    return router


def competent_authorities_router(tag: str, audience: Role) -> APIRouter:
    """`GET /competent-authorities`, `/competent-authorities/count`."""
    router = APIRouter(tags=[tag])
    roles = [Depends(RequireRoles(audience, Role.READ))]

    @router.get(
        "/competent-authorities",
        response_model=CompetentAuthorityListResponse,
        status_code=status.HTTP_200_OK,
        summary=docs.COMPETENT_AUTHORITIES_SUMMARY,
        description=docs.COMPETENT_AUTHORITIES_DESCRIPTION,
        operation_id="getCompetentAuthorities",
        responses=docs.COMPETENT_AUTHORITIES_RESPONSES,
        dependencies=roles,
    )
    async def get_competent_authorities(
        pagination: LimitedPaginationDependency,
        session: AsyncSession = Depends(get_async_db_read_only),
    ) -> CompetentAuthorityListResponse:
        competent_authorities = (
            await competent_authority_service.get_competent_authorities(
                session, offset=pagination.offset, limit=pagination.limit
            )
        )
        return CompetentAuthorityListResponse(
            competent_authorities=[
                CompetentAuthorityResponse.model_validate(ca)
                for ca in competent_authorities
            ]
        )

    @router.get(
        "/competent-authorities/count",
        response_model=CompetentAuthorityCountResponse,
        status_code=status.HTTP_200_OK,
        summary=docs.COUNT_COMPETENT_AUTHORITIES_SUMMARY,
        description=docs.COUNT_COMPETENT_AUTHORITIES_SUMMARY,
        operation_id="countCompetentAuthorities",
        responses=_COUNT_RESPONSES,
        dependencies=roles,
    )
    async def count_competent_authorities(
        session: AsyncSession = Depends(get_async_db_read_only),
    ) -> CompetentAuthorityCountResponse:
        return CompetentAuthorityCountResponse(
            count=await competent_authority_service.count_competent_authorities(session)
        )

    return router


def areas_router(tag: str, audience: Role) -> APIRouter:
    """`GET /areas`, `/areas/count`, same as STR v2 (without the shapefile download)."""
    router = APIRouter(tags=[tag])
    roles = [Depends(RequireRoles(audience, Role.READ))]

    @router.get(
        "/areas",
        response_model=AreaListResponse,
        status_code=status.HTTP_200_OK,
        summary=AREAS_SUMMARY,
        description=AREAS_DESCRIPTION_V2,
        operation_id="getAreas",
        responses=AREAS_RESPONSES,
        dependencies=roles,
    )
    async def get_areas(
        pagination: LimitedPaginationDependency,
        session: AsyncSession = Depends(get_async_db_read_only),
    ) -> AreaListResponse:
        areas = await area_service.get_areas(
            session, offset=pagination.offset, limit=pagination.limit
        )
        return AreaListResponse(areas=[AreaResponse.model_validate(a) for a in areas])

    @router.get(
        "/areas/count",
        response_model=AreaCountResponse,
        status_code=status.HTTP_200_OK,
        summary="Get areas count (optional, to support pagination)",
        description="Get areas count (optional, to support pagination).",
        operation_id="countAreas",
        responses=_COUNT_RESPONSES,
        dependencies=roles,
    )
    async def count_areas(
        session: AsyncSession = Depends(get_async_db_read_only),
    ) -> AreaCountResponse:
        return AreaCountResponse(count=await area_service.count_areas(session))

    return router
