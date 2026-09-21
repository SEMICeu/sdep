"""HTTP status mapping for the bulk activities result, shared by STR v1 and v2."""

from fastapi import status
from fastapi.responses import JSONResponse

from app.schemas.activity_bulk import ActivityBulkResponse


def bulk_json_response(result: ActivityBulkResponse) -> JSONResponse:
    """201 when every item succeeded, 200 on partial success, 422 when all failed."""
    if result.failed == 0:
        http_status = status.HTTP_201_CREATED
    elif result.succeeded > 0:
        http_status = status.HTTP_200_OK
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_CONTENT

    return JSONResponse(
        status_code=http_status,
        content=result.model_dump(by_alias=True, mode="json"),
    )
