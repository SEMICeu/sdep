"""STR v2 bulk listing acknowledgements endpoint (random check performed).

Transaction pattern: see activities_bulk_v1.py.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import ClientDependency, RequireRoles
from app.api.common.bulk_json import bulk_json_response
from app.api.common.security import Role
from app.api.domains.str.routers.listings_docs import (
    ACK_DESCRIPTION,
    ACK_OPENAPI_EXTRA,
    ACK_RESPONSES,
    ACK_SUMMARY,
)
from app.db.config import get_async_db
from app.schemas.listing_bulk import (
    ListingAcknowledgementBulkRequest,
    ListingAcknowledgementBulkResponse,
)
from app.services import listing_acknowledgement_bulk as acknowledgement_service

router = APIRouter(tags=["str"])


@router.post(
    "/listing-acknowledgements/bulk",
    summary=ACK_SUMMARY,
    description=ACK_DESCRIPTION,
    operation_id="postListingAcknowledgementsBulkV2",
    response_model=ListingAcknowledgementBulkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ACK_RESPONSES,
    openapi_extra=ACK_OPENAPI_EXTRA,
    dependencies=[Depends(RequireRoles(Role.STR, Role.WRITE))],
)
async def post_listing_acknowledgements_bulk(
    request: ListingAcknowledgementBulkRequest,
    client: ClientDependency,
    session: AsyncSession = Depends(get_async_db, scope="function"),
) -> Response:
    """
    Acknowledge flagged listings in bulk.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_write" roles in realm_access
    - Platform extracted from token's "client_id" claim
    """
    result = await acknowledgement_service.acknowledge_listings_bulk(
        session=session,
        acknowledgements_raw=cast("list[dict[str, Any]]", request.acknowledgements),
        client_id=client.id,
    )
    return bulk_json_response(result)
