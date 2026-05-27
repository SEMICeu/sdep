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
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common.auth_dependencies import (
    ClientDependency,
    NamedClientDependency,
    RequireRoles,
)
from app.api.common.filename import (
    content_disposition_header,
    sanitize_download_filename,
    sanitize_upload_filename,
)
from app.api.common.security import Role
from app.db.config import get_async_db, get_async_db_read_only
from app.schemas.area import (
    AreaCountResponse,
    AreaListResponse,
    AreaResponse,
    OptionalRegulation,
)
from app.schemas.common import (
    FunctionalId,
    OptionalFunctionalId,
)
from app.schemas.error import ErrorResponse
from app.security.malware_scan import scan_file_for_malware
from app.services import area as area_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ca"])

MAX_FILE_SIZE = 1048576  # 1 MiB
# Multipart envelope adds boundary markers and per-part headers around the file.
# 64 KiB headroom is far larger than any realistic single-field multipart overhead
# (~hundreds of bytes), and keeps us from false-rejecting borderline uploads.
MAX_REQUEST_SIZE = MAX_FILE_SIZE + 64 * 1024
ZIP_MAGIC = b"PK\x03\x04"


@router.post(
    "/areas",
    summary="Submit a single area into the areas collection for the currently authenticated competent authority",
    description="""Submit a single area into the areas collection for the currently authenticated competent authority.

**ID Pattern:**
- `areaId`: provided by competent authority as business identifier (optional), otherwise generated as UUIDv4 (RFC 9562)

**Versioning:**
- Same `areaId` can be resubmitted → creates new version with different timestamp
- Unique constraint: (areaId, createdAt, current authenticated competent authority)

**Limiting:**
- Only `.zip` files are accepted (validated by filename extension and file content)
- Max. 1 MiB (1,048,576 bytes) per file
- This is to ensure predictable performance, reduce abuse risk, and improve overall reliability

**The request contains (multipart/form-data):**
- `areaId`: Functional ID identifying this area (alphanumeric with hyphens `^[A-Za-z0-9\\-]+$`, max 64 chars, optionally supplied, auto-generated as UUIDv4 RFC 9562 if not supplied)
- `areaName`: Display name (optional, max 64 chars)
- `regulation`: Regulation type of the area - 'listing', 'activity', or 'all' (optional, defaults to 'all' when not supplied)
- `file`: Shapefile upload (.zip only, max 1 MiB)

**The response contains:**
- `areaId`: Functional ID identifying this area
- `areaName`: Display name (optional) of the area
- `regulation`: Regulation type of the area - 'listing', 'activity', or 'all'
- `filename`: Name of the area shapefile (e.g., 'area.zip')
- `competentAuthorityId`: Functional ID of the competent authority that owns the area
- `competentAuthorityName`: Display name (optional) of the competent authority
- `createdAt`: Timestamp when this area version was created (UTC)

""",
    operation_id="postArea",
    response_model=AreaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        "201": {
            "description": "Area created successfully",
            "model": AreaResponse,
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
            "description": "Validation Error - business rule violation",
        },
    },
    dependencies=[Depends(RequireRoles(Role.CA, Role.WRITE))],
)
async def post_area(
    request: Request,
    client: NamedClientDependency,
    session: AsyncSession = Depends(get_async_db),
    areaId: Annotated[OptionalFunctionalId, Form()] = None,
    areaName: str | None = Form(None),
    regulation: Annotated[OptionalRegulation, Form()] = None,
    file: UploadFile = File(...),
) -> Response:
    """
    Submit a single area with file upload.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_write" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    - Competent authority name extracted from token's "client_name" claim
    """
    # Fail fast on oversize uploads using the advertised Content-Length, before
    # buffering the body. The exact file-size check still runs after read()
    # because Content-Length covers the whole multipart envelope, not the file.
    content_length_header = request.headers.get("content-length")
    if content_length_header is not None:
        try:
            advertised_length = int(content_length_header)
        except ValueError:
            advertised_length = None
        if advertised_length is not None and advertised_length > MAX_REQUEST_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    f"Request body exceeds maximum size of 1 MiB ({MAX_FILE_SIZE} bytes). "
                    f"Advertised Content-Length: {advertised_length} bytes."
                ),
            )

    # Read and validate file
    raw_filename = file.filename or "unnamed"
    filename = sanitize_upload_filename(raw_filename)

    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .zip files are accepted.",
        )

    base_name = filename[: -len(".zip")]
    if not base_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Filename is invalid: it must contain a name before the .zip extension.",
        )

    if len(filename) > 64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Filename must be at most 64 characters.",
        )

    filedata = await file.read()
    if len(filedata) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File exceeds maximum size of 1 MiB ({MAX_FILE_SIZE} bytes). Received {len(filedata)} bytes.",
        )
    malware_scan_results = await scan_file_for_malware(filedata)
    if not malware_scan_results.passed_malware_scan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file may contain malicious content.",
        )

    if not filedata.startswith(ZIP_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File is not a valid ZIP archive: mismatch in the identifying first bytes (the magic bytes).",
        )

    # Normalize empty strings to None
    area_id = areaId if areaId != "" else None
    area_name = areaName if areaName != "" else None

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
        regulation=regulation,
        filename=filename,
        filedata=filedata,
        client_id=client.id,
        competent_authority_name=client.name,
    )

    response = AreaResponse(
        area_id=area_obj.area_id,
        area_name=area_obj.area_name,
        regulation=area_obj.regulation,
        filename=area_obj.filename,
        competent_authority_id=area_obj.competent_authority.competent_authority_id,
        competent_authority_name=area_obj.competent_authority.competent_authority_name,
        created_at=area_obj.created_at,
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/areas",
    summary="Get areas for the currently authenticated competent authority",
    description="""Get all areas owned by the currently authenticated competent authority. By default, returns all areas (unlimited). Use optional pagination parameters to limit results.

**Scoping:**
- Only returns areas belonging to the currently authenticated competent authority (based on JWT client_id)

**Each area contains:**
- `areaId`: Functional ID identifying this area
- `areaName`: Display name (optional) of the area
- `regulation`: Regulation type: 'listing', 'activity', or 'all'
- `filename`: Name of the area shapefile (e.g., 'area.zip')
- `competentAuthorityId`: Functional ID of the competent authority that owns the area
- `competentAuthorityName`: Display name (optional) of the competent authority
- `createdAt`: Timestamp when this area version was created (UTC)

**Pagination:**
- `offset`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: unlimited)

""",
    operation_id="getOwnAreas",
    response_model=AreaListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        "200": {
            "description": "List of areas owned by the authenticated competent authority",
            "model": AreaListResponse,
            "content": {
                "application/json": {
                    "example": {
                        "areas": [
                            {
                                "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
                                "areaName": "Amsterdam",
                                "regulation": "all",
                                "filename": "Amsterdam.zip",
                                "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
                                "competentAuthorityName": "Amsterdam (inclusief Weesp)",
                                "createdAt": "2025-01-01T00:00:00Z",
                            },
                        ],
                    }
                }
            },
        },
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
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_own_areas(
    client: ClientDependency,
    session: AsyncSession = Depends(get_async_db_read_only),
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
    Get areas for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    """
    # Get areas for this CA
    area_objects = await area_service.get_areas_by_client_id(
        session,
        client_id=client.id,
        offset=offset,
        limit=limit,
    )

    areas = [AreaResponse.model_validate(area_obj) for area_obj in area_objects]

    response = AreaListResponse(areas=areas)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/areas/count",
    response_model=AreaCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get areas count for the currently authenticated competent authority (optional, to support pagination)",
    description="Get areas count for the currently authenticated competent authority (optional, to support pagination).",
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
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def count_own_areas(
    client: ClientDependency,
    session: AsyncSession = Depends(get_async_db_read_only),
) -> AreaCountResponse:
    """
    Count areas for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns:
    - count: Total number of areas for the given competent authority
    """
    # Call business service with competent authority ID from token
    total_count = await area_service.count_areas_by_client_id(session, client.id)

    return AreaCountResponse(count=total_count)


@router.get(
    "/areas/{areaId}",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get area (shapefile) for the currently authenticated competent authority",
    description="Get area (shapefile) based on functional ID, scoped to the currently authenticated competent authority.",
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
    dependencies=[Depends(RequireRoles(Role.CA, Role.READ))],
)
async def get_own_area(
    client: ClientDependency,
    areaId: Annotated[FunctionalId, Path(...)],
    session: AsyncSession = Depends(get_async_db_read_only),
) -> Response:
    """
    Get specific area for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_read" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim

    Returns raw binary area, or 404 if not found / not owned by the CA.
    """
    # Get the area scoped to this CA
    area_data = await area_service.get_area_by_area_id_and_client_id(
        session,
        area_id=areaId,
        client_id=client.id,
    )

    if area_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with areaId '{areaId}' not found",
        )

    # Return raw binary data (or empty bytes if filedata is None)
    binary_data = area_data.filedata if area_data.filedata is not None else b""
    filename = sanitize_download_filename(area_data.filename)

    return Response(
        content=binary_data,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition_header(filename)},
    )


@router.delete(
    "/areas/{areaId}",
    summary="Delete (deactivate) an area from the areas collection for the currently authenticated competent authority",
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
            "description": "Validation Error - business rule violation",
        },
    },
    dependencies=[Depends(RequireRoles(Role.CA, Role.WRITE))],
)
async def delete_area(
    client: ClientDependency,
    areaId: Annotated[FunctionalId, Path(...)],
    session: AsyncSession = Depends(get_async_db),
) -> Response:
    """
    Delete (deactivate) an area for the currently authenticated competent authority.

    Authorization:
    - Requires valid bearer token with "sdep_ca" and "sdep_write" roles in realm_access
    - Competent authority ID extracted from token's "client_id" claim
    """
    # Delete the area (deactivate)
    await area_service.delete_area_by_client_id(
        session=session,
        area_id=areaId,
        client_id=client.id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
