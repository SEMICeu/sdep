"""Ping endpoint"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.schemas.auth import UnauthorizedError
from app.schemas.health import Status
from app.security import verify_bearer_token

router = APIRouter(tags=["health"])


@router.get(
    "/ping",
    response_model=Status,
    status_code=status.HTTP_200_OK,
    summary="Ping application (authenticated)",
    description="Verify if API is reachable (requires authentication)",
    operation_id="ping",
    responses={
        "401": {
            "model": UnauthorizedError,
            "description": "Unauthorized - Invalid or missing token",
        },
    },
)
async def ping(token_payload: dict[str, Any] = Depends(verify_bearer_token)) -> Status:
    """Verify if API is reachable (requires valid bearer token)"""
    return Status(status="OK")
