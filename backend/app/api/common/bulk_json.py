"""HTTP status mapping for bulk results, shared by every bulk endpoint."""

from typing import Any, Protocol

from fastapi import status
from fastapi.responses import JSONResponse


class BulkResult(Protocol):
    """What a bulk response must offer: the counts and a JSON dump."""

    @property
    def succeeded(self) -> int: ...

    @property
    def failed(self) -> int: ...

    def model_dump(self, *, by_alias: bool, mode: str) -> dict[str, Any]: ...


def bulk_json_response(result: BulkResult) -> JSONResponse:
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
