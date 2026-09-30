"""Listing screening authority (LSA) bulk screenings endpoint for API v2.

Transaction pattern: see str/routers/activities_bulk_v1.py.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import RequireRoles
from app.api.common.bulk_json import bulk_json_response
from app.api.common.security import Role
from app.api.domains.lsa.routers.listings_docs import (
    SCREENING_DESCRIPTION,
    SCREENING_OPENAPI_EXTRA,
    SCREENING_RESPONSES,
    SCREENING_SUMMARY,
)
from app.db.config import get_async_db
from app.schemas.listing_bulk import (
    ListingScreeningBulkRequest,
    ListingScreeningBulkResponse,
)
from app.services import listing_screening_bulk as screening_service

router = APIRouter(tags=["lsa"])


@router.post(
    "/listing-screenings/bulk",
    summary=SCREENING_SUMMARY,
    description=SCREENING_DESCRIPTION,
    operation_id="postListingScreeningsBulk",
    response_model=ListingScreeningBulkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=SCREENING_RESPONSES,
    openapi_extra=SCREENING_OPENAPI_EXTRA,
    dependencies=[Depends(RequireRoles(Role.LSA, Role.WRITE))],
)
async def post_listing_screenings_bulk(
    request: ListingScreeningBulkRequest,
    session: AsyncSession = Depends(get_async_db, scope="function"),
) -> Response:
    """
    Submit screening results in bulk.

    Authorization:
    - Requires valid bearer token with "sdep_lsa" and "sdep_write" roles in realm_access
    - The platform is named per item (`platformId`), not taken from the token
    """
    result = await screening_service.screen_listings_bulk(
        session=session,
        screenings_raw=cast("list[dict[str, Any]]", request.screenings),
    )
    return bulk_json_response(result)
