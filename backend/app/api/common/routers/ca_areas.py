"""CA Area endpoints.

Transaction Management Architecture (API Layer):
- This API endpoint uses get_async_db for automatic transaction management
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes, never commits

Pattern:
- API layer: Transaction boundary (auto-commit via dependency)
- Service layer: Business logic (no transaction management)
- CRUD layer: Data access (flush only, no commits)
"""

import logging
import re
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_async_db, get_async_db_read_only
from app.schemas.area import (
    AreaCountResponse,
    AreaOwnListResponse,
    AreaOwnResponse,
)
from app.schemas.error import ErrorResponse
from app.security import verify_bearer_token
from app.services import area as area_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ca"])

AREA_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")
MAX_FILE_SIZE = 1048576  # 1 MiB


@router.post(
    "/ca/areas",
    summary="Submit a single area into the areas collection for the current authenticated competent authority",
    description="""Submit a single area into the areas collection for the current authenticated competent authority (competentAuthorityId).

**ID Pattern:**
- `areaId`: provided by competent authority as business identifier (optional), otherwise generated as UUID (RFC 9562)

**Versioning:**
- Same `areaId` can be resubmitted → creates new version with different timestamp
- Unique constraint: (areaId, createdAt, competent authority)

**Limiting:**
- Max. 1 MiB (1,048,576 bytes) per file
- This is to ensure predictable performance, reduce abuse risk, and improve overall reliability

**The request contains (multipart/form-data):**
- `areaId`: Functional ID identifying this area (optional, auto-generated UUID if not provided; lowercase alphanumeric with hyphens `^[a-z0-9-]+$`, max 64 chars)
- `areaName`: Optional human-readable name for this area (optional, max 64 chars)
- `file`: Shapefile upload (required, max 1 MiB)

**The response contains:**
- `areaId`: Functional ID identifying this area
- `areaName`: Optional human-readable name for this area
- `filename`: Name of the shapefile (e.g., 'area.zip')
- `createdAt`: Timestamp when this area version was created (UTC)

""",
    operation_id="postArea",
    response_model=AreaOwnResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        "201": {
            "description": "Area created successfully",
            "model": AreaOwnResponse,
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
        "422": {
            "model": ErrorResponse,
            "description": "Validation Error - busines rule violation",
        },
    },
)
async def post_area(
    session: AsyncSession = Depends(get_async_db),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
    areaId: str | None = Form(None),
    areaName: str | None = Form(None),
    file: UploadFile = File(...),
) -> Response:
    """
    Submit a single area with file upload.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_write" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    - Competent authority name extracted from token's "client_name" claim
    """

    # Authorization check: Verify user has "sdep_ca" and "sdep_write" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_write" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_write' role required",
        )

    # Extract competent authority ID and name from token
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    competent_authority_name = token_payload.get("client_name")
    if not competent_authority_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_name' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Read and validate file
    filedata = await file.read()
    if len(filedata) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File exceeds maximum size of 1 MiB ({MAX_FILE_SIZE} bytes). Received {len(filedata)} bytes.",
        )

    filename = file.filename or "unnamed"

    # Normalize empty strings to None
    area_id = areaId if areaId != "" else None
    area_name = areaName if areaName != "" else None

    # Validate areaId format
    if area_id is not None:
        if len(area_id) > 64:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="areaId must be at most 64 characters.",
            )
        if not AREA_ID_PATTERN.match(area_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="areaId must match pattern ^[a-z0-9-]+$ (lowercase alphanumeric with hyphens).",
            )

    # Validate areaName length
    if area_name is not None and len(area_name) > 64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="areaName must be at most 64 characters.",
        )

    # Create the area
    area_obj = await area_service.create_area(
        session=session,
        area_id=area_id,
        area_name=area_name,
        filename=filename,
        filedata=filedata,
        competent_authority_id_str=competent_authority_id,
        competent_authority_name=competent_authority_name,
    )

    # Build response
    response = AreaOwnResponse(
        areaId=area_obj.area_id,
        areaName=area_obj.area_name,
        filename=area_obj.filename,
        createdAt=area_obj.created_at,
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/ca/areas",
    summary="Get areas for the current authenticated competent authority",
    description="""Get all areas submitted by the current authenticated competent authority. By default, returns all areas (unlimited). Use optional pagination parameters to limit results.

**Scoping:**
- Only returns areas belonging to the authenticated CA (based on JWT client_id)

**Each area contains:**
- `areaId`: Functional ID identifying this area
- `areaName`: Optional human-readable name for this area
- `filename`: Name of the shapefile (e.g., 'area.zip')
- `createdAt`: Timestamp when this area version was created (UTC)

**Pagination:**
- `offset`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: unlimited)

""",
    operation_id="getOwnAreas",
    response_model=AreaOwnListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        "400": {
            "model": ErrorResponse,
            "description": "Bad request - invalid query parameters",
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
    },
)
async def get_own_areas(
    session: AsyncSession = Depends(get_async_db),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
    offset: Annotated[
        int, Query(ge=0, description="Number of records to skip (default: 0)")
    ] = 0,
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=1000,
            description="Maximum number of records to return (default: unlimited, max: 1000 when specified)",
        ),
    ] = None,
) -> Response:
    """
    Get areas for the current authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    """

    # Authorization check: Verify user has "sdep_ca" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract competent authority ID from token
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get areas for this CA
    area_dicts = await area_service.get_areas_by_competent_authority(
        session,
        competent_authority_id_str=competent_authority_id,
        offset=offset,
        limit=limit,
    )

    # Build response
    areas = [
        AreaOwnResponse(
            areaId=area_dict["areaId"],
            areaName=area_dict["areaName"],
            filename=area_dict["filename"],
            createdAt=area_dict["createdAt"],
        )
        for area_dict in area_dicts
    ]

    response = AreaOwnListResponse(areas=areas)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/ca/areas/count",
    response_model=AreaCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get areas count for the current authenticated competent authority (optional, to support pagination)",
    description="Get areas count for the current authenticated competent authority (optional, to support pagination)",
    operation_id="countOwnAreas",
    responses={
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
    },
)
async def count_own_areas(
    session: AsyncSession = Depends(get_async_db_read_only),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> AreaCountResponse:
    """
    Count areas for the current authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns:
    - count: Total number of areas for the given competent authority
    """
    # Authorization check: Verify user has "sdep_ca" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract competent authority ID from token's client_id claim
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Call business service with competent authority ID from token
    total_count = await area_service.count_areas_by_competent_authority(
        session, competent_authority_id
    )

    return AreaCountResponse(count=total_count)


@router.get(
    "/ca/areas/{areaId}",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get area (shapefile) for the current authenticated competent authority",
    description="Get area (shapefile) based on functional ID, scoped to the authenticated CA",
    operation_id="getOwnArea",
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
            "description": "Resource Not Found - area unavailable, deleted, or not owned by this CA",
        },
    },
)
async def get_own_area(
    areaId: str,
    session: AsyncSession = Depends(get_async_db_read_only),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> Response:
    """
    Get specific area for the current authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns raw binary area, or 404 if not found / not owned by the CA.
    """
    # Authorization check: Verify user has "sdep_ca" and "sdep_read" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_read" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_read' role required",
        )

    # Extract competent authority ID from token
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the area scoped to this CA
    area_data = await area_service.get_own_area_by_id(
        session,
        area_id=areaId,
        competent_authority_id_str=competent_authority_id,
    )

    if area_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with areaId '{areaId}' not found",
        )

    # Return raw binary data (or empty bytes if filedata is None)
    binary_data = area_data["filedata"] if area_data["filedata"] is not None else b""
    filename = area_data.get("filename", "area.zip")

    return Response(
        content=binary_data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/ca/areas/{areaId}",
    summary="Delete (deactivate) an area from the areas collection for the current authenticated competent authority",
    description="""Delete (deactivate) an area by marking it as ended (now, UTC).

**Behavior:**
- Deletes (deactivates) the area
- The area will no longer appear in area listings
- Deleting an already-deleted area returns 404

""",
    operation_id="deleteOwnArea",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        "204": {
            "description": "Success - area deleted (deactivate)",
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - missing or invalid token",
        },
        "403": {
            "description": "Forbidden - insufficient permissions",
        },
        "404": {
            "description": "Resource Not Found - area unavailable, already deleted, or not owned by this CA",
        },
        "422": {
            "model": ErrorResponse,
            "description": "Validation Error - busines rule violation",
        },
    },
)
async def delete_area(
    areaId: str,
    session: AsyncSession = Depends(get_async_db),
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> Response:
    """
    Delete (deactivate) an area for the current authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_write" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    """

    # Authorization check: Verify user has "sdep_ca" and "sdep_write" roles
    realm_access = token_payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if "sdep_ca" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_ca' role required",
        )

    if "sdep_write" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: 'sdep_write' role required",
        )

    # Extract competent authority ID from token
    competent_authority_id = token_payload.get("client_id")
    if not competent_authority_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate areaId format
    if len(areaId) > 64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="areaId must be at most 64 characters.",
        )
    if not AREA_ID_PATTERN.match(areaId):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="areaId must match pattern ^[a-z0-9-]+$ (lowercase alphanumeric with hyphens).",
        )

    # Delete the area (deactivate)
    await area_service.delete_area(
        session=session,
        area_id=areaId,
        competent_authority_id_str=competent_authority_id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
