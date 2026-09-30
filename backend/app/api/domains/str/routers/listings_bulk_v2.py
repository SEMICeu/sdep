"""STR v2 bulk listings endpoint (random checks).

Transaction pattern: see activities_bulk_v1.py.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import NamedClientDependency, RequireRoles
from app.api.common.bulk_json import bulk_json_response
from app.api.common.security import Role
from app.api.domains.str.routers.listings_docs import (
    BULK_DESCRIPTION,
    BULK_OPENAPI_EXTRA,
    BULK_RESPONSES,
    BULK_SUMMARY,
)
from app.db.config import get_async_db
from app.schemas.listing_bulk import ListingBulkRequest, ListingBulkResponse
from app.services import listing_bulk as listing_bulk_service

router = APIRouter(tags=["str"])


@router.post(
    "/listings/bulk",
    summary=BULK_SUMMARY,
    description=BULK_DESCRIPTION,
    operation_id="postListingsBulkV2",
    response_model=ListingBulkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=BULK_RESPONSES,
    openapi_extra=BULK_OPENAPI_EXTRA,
    dependencies=[Depends(RequireRoles(Role.STR, Role.WRITE))],
)
async def post_listings_bulk(
    request: ListingBulkRequest,
    client: NamedClientDependency,
    session: AsyncSession = Depends(get_async_db, scope="function"),
) -> Response:
    """
    Submit randomly selected listings in bulk.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_write" roles in realm_access
    - Platform ID extracted from token's "client_id" claim
    - Platform name extracted from token's "client_name" claim
    """
    # `listings` is typed for the OpenAPI contract but uses `SkipValidation`, so
    # at runtime items are raw dicts - cast to match the service signature.
    result = await listing_bulk_service.create_listings_bulk(
        session=session,
        listings_raw=cast("list[dict[str, Any]]", request.listings),
        client_id=client.id,
        platform_name=client.name,
    )
    return bulk_json_response(result)
