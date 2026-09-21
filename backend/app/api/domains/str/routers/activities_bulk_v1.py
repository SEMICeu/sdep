"""STR v1 bulk activities endpoint.

Transaction Management Architecture (API Layer):
- This API endpoint uses get_async_db for automatic transaction management
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes, never commits

Pattern:
- API layer: Transaction boundary (auto-commit via dependency)
- Service layer: Business logic (no transaction management)
- CRUD layer: Data access (flush only, no commits)
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import NamedClientDependency, RequireRoles
from app.api.common.security import Role
from app.api.domains.str.routers.activities_bulk_docs import (
    BULK_DESCRIPTION_V1,
    BULK_OPENAPI_EXTRA,
    BULK_RESPONSES,
    BULK_SUMMARY,
)
from app.api.domains.str.routers.activities_bulk_shared import bulk_json_response
from app.db.config import get_async_db
from app.schemas.activity_bulk import ActivityBulkRequest, ActivityBulkResponse
from app.services import activity_bulk as activity_bulk_service

router = APIRouter(tags=["str"])


@router.post(
    "/activities/bulk",
    summary=BULK_SUMMARY,
    description=BULK_DESCRIPTION_V1,
    operation_id="postActivitiesBulk",
    response_model=ActivityBulkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=BULK_RESPONSES,
    openapi_extra=BULK_OPENAPI_EXTRA,
    dependencies=[Depends(RequireRoles(Role.STR, Role.WRITE))],
)
async def post_activities_bulk(
    request: ActivityBulkRequest,
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
    # `activities` is typed as `list[ActivityRequest]` for the OpenAPI contract
    # but uses `SkipValidation`, so at runtime items are raw dicts - cast to
    # match the service signature.
    result = await activity_bulk_service.create_activities_bulk(
        session=session,
        activities_raw=cast("list[dict[str, Any]]", request.activities),
        client_id=client.id,
        platform_name=client.name,
    )
    return bulk_json_response(result)
