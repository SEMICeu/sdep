"""Upload size limit, enforced before the request body is parsed."""

import re

from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas.error import ErrorDetail, ErrorResponse


def _too_large_detail(max_bytes: int, received: int) -> str:
    return (
        f"Request body exceeds maximum size of {max_bytes} bytes. "
        f"Received at least {received} bytes."
    )


class UploadSizeLimitMiddleware:
    """Reject an oversize upload with 413 before FastAPI buffers it.

    FastAPI parses `File`/`Form` parameters before the endpoint runs, so a size
    check in the endpoint comes too late. This checks `Content-Length` up front,
    and counts the bytes of a body that streams in without it.
    """

    def __init__(self, app: ASGIApp, max_bytes: int, path_pattern: str) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.path_pattern = re.compile(path_pattern)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not self.path_pattern.fullmatch(scope["path"])
        ):
            await self.app(scope, receive, send)
            return

        advertised = _content_length(scope)
        if advertised is not None and advertised > self.max_bytes:
            await self._reject(send, advertised)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI passes an HTTPException from body parsing through
                    # unchanged, so the domain's handler returns this 413.
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=_too_large_detail(self.max_bytes, received),
                    )
            return message

        await self.app(scope, limited_receive, send)

    async def _reject(self, send: Send, received: int) -> None:
        body = (
            ErrorResponse(
                detail=[
                    ErrorDetail(
                        msg=_too_large_detail(self.max_bytes, received),
                        type="validation_error",
                    )
                ]
            )
            .model_dump_json(exclude_none=True)
            .encode()
        )
        await send(
            {
                "type": "http.response.start",
                "status": status.HTTP_413_CONTENT_TOO_LARGE,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _content_length(scope: Scope) -> int | None:
    """The advertised Content-Length, or None when absent or malformed."""
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
