"""STR v2 bulk activities endpoint.

Differs from v1 in the item schema (UTC-only timestamps) and the
regulation check. Transaction pattern: see activities_bulk_v1.py.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import NamedClientDependency, RequireRoles
from app.api.common.security import Role
from app.api.domains.str.routers.activities_bulk_docs import (
    BULK_DESCRIPTION_V2,
    BULK_OPENAPI_EXTRA,
    BULK_RESPONSES,
    BULK_SUMMARY,
)
from app.api.domains.str.routers.activities_bulk_shared import bulk_json_response
from app.db.config import get_async_db
from app.schemas.activity import ActivityRequestV2
from app.schemas.activity_bulk import ActivityBulkRequestV2, ActivityBulkResponse
from app.services import activity_bulk as activity_bulk_service

router = APIRouter(tags=["str"])


@router.post(
    "/activities/bulk",
    summary=BULK_SUMMARY,
    description=BULK_DESCRIPTION_V2,
    operation_id="postActivitiesBulkV2",
    response_model=ActivityBulkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=BULK_RESPONSES,
    openapi_extra=BULK_OPENAPI_EXTRA,
    dependencies=[Depends(RequireRoles(Role.STR, Role.WRITE))],
)
async def post_activities_bulk(
    request: ActivityBulkRequestV2,
    client: NamedClientDependency,
    session: AsyncSession = Depends(get_async_db),
) -> Response:
    """
    Submit rental activities in bulk.

    Authorization:
    - Requires valid bearer token with "sdep_str" and "sdep_write" roles in realm_access
    - Platform ID extracted from token's "client_id" claim
    - Platform name extracted from token's "client_name" claim
    """
    # `activities` is typed as `list[ActivityRequestV2]` for the OpenAPI contract
    # but uses `SkipValidation`, so at runtime items are raw dicts - cast to
    # match the service signature.
    result = await activity_bulk_service.create_activities_bulk(
        session=session,
        activities_raw=cast("list[dict[str, Any]]", request.activities),
        client_id=client.id,
        platform_name=client.name,
        item_model=ActivityRequestV2,
        require_activity_regulation=True,
    )
    return bulk_json_response(result)
