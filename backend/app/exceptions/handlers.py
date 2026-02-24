"""Global exception handlers for consistent error responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorDetail, ErrorResponse

if TYPE_CHECKING:
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError as PydanticValidationError
    from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

    from app.exceptions.auth import (
        AuthenticationError,
        AuthorizationError,
        InvalidTokenError,
    )
    from app.exceptions.business import (
        ApplicationValidationError,
        ResourceNotFoundError,
    )
    from app.exceptions.infrastructure import (
        AuthorizationServerOperationalError,
        DatabaseOperationalError,
    )


def _get_logger():
    """Lazy import logger to avoid circular dependencies."""
    import logging

    return logging.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError | PydanticValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Returns 400 Bad Request for GET requests (query parameter validation),
    Returns 422 Unprocessable Entity for other methods (request body validation).
    """
    logger = _get_logger()
    logger.warning(f"Validation error on {request.url.path}: {exc}")

    # Standard error response
    details = []
    for error in exc.errors():
        details.append(
            ErrorDetail(
                msg=error["msg"],
                type=error["type"],
            )
        )

    # Use 400 for GET requests (query param validation), 422 for others (body validation)
    status_code = (
        status.HTTP_400_BAD_REQUEST
        if request.method == "GET"
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )

    error_response = ErrorResponse(
        detail=details,
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json"),
    )


async def business_logic_exception_handler(
    request: Request, exc: ApplicationValidationError
) -> JSONResponse:
    """Handle business logic errors."""
    logger = _get_logger()
    logger.warning(f"Business logic error on {request.url.path}: {exc}")

    # Import here to avoid circular dependency
    from app.exceptions.business import DuplicateResourceError

    # Use 409 Conflict for duplicate resources, 422 for other business errors
    if isinstance(exc, DuplicateResourceError):
        error_type = "duplicate_error"
        status_code = status.HTTP_409_CONFLICT
    else:
        error_type = "business_logic_error"
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    error_response = ErrorResponse(
        detail=[ErrorDetail(msg=str(exc), type=error_type)],
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json"),
    )


async def authentication_exception_handler(
    request: Request, exc: AuthenticationError | InvalidTokenError
) -> JSONResponse:
    """Handle authentication errors."""
    logger = _get_logger()
    logger.warning(f"Authentication error on {request.url.path}: {exc}")

    error_response = ErrorResponse(
        detail=[
            ErrorDetail(
                msg="Token is invalid or expired",
                type="authentication_error",
            )
        ],
    )

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response.model_dump(mode="json"),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_exception_handler(
    request: Request, exc: AuthorizationError
) -> JSONResponse:
    """Handle authorization errors."""
    logger = _get_logger()
    logger.warning(f"Authorization error on {request.url.path}: {exc}")

    error_response = ErrorResponse(
        detail=[ErrorDetail(msg=str(exc), type="authorization_error")],
    )

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=error_response.model_dump(mode="json"),
    )


async def resource_not_found_exception_handler(
    request: Request, exc: ResourceNotFoundError
) -> JSONResponse:
    """Handle resource not found errors."""
    logger = _get_logger()
    logger.warning(f"Resource not found error on {request.url.path}: {exc}")

    error_response = ErrorResponse(
        detail=[ErrorDetail(msg=str(exc), type="not_found_error")],
    )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response.model_dump(mode="json"),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with proper formatting."""
    logger = _get_logger()

    # Determine the error type based on status code
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        error_type = "authentication_error"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        error_type = "authorization_error"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        error_type = "not_found_error"
    elif exc.status_code == status.HTTP_409_CONFLICT:
        error_type = "duplicate_error"
    elif 400 <= exc.status_code < 500:
        error_type = "validation_error"
    else:
        error_type = "server_error"

    logger.warning(
        f"HTTP exception on {request.url.path}: {exc.detail} (status: {exc.status_code})"
    )

    error_response = ErrorResponse(
        detail=[ErrorDetail(msg=str(exc.detail), type=error_type)],
    )

    response = JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode="json"),
    )

    # Include WWW-Authenticate header for 401 errors
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        response.headers["WWW-Authenticate"] = "Bearer"

    return response


async def database_unavailable_exception_handler(
    request: Request, exc: DatabaseOperationalError | SQLAlchemyOperationalError
) -> JSONResponse:
    """Handle database operational errors (DB connection failures) as 503."""
    logger = _get_logger()
    logger.error(f"Database unavailable on {request.url.path}: {exc}")

    error_response = ErrorResponse(
        detail=[
            ErrorDetail(
                msg="Database is temporarily unavailable", type="service_unavailable"
            )
        ],
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_response.model_dump(mode="json"),
    )


async def authorization_server_unavailable_exception_handler(
    request: Request, exc: AuthorizationServerOperationalError
) -> JSONResponse:
    """Handle authorization server (Keycloak) unavailability as 503."""
    logger = _get_logger()
    logger.error(f"Authorization server unavailable on {request.url.path}: {exc}")

    error_response = ErrorResponse(
        detail=[
            ErrorDetail(
                msg="Authorization server is temporarily unavailable",
                type="service_unavailable",
            )
        ],
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_response.model_dump(mode="json"),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions.

    This is the catch-all handler that prevents stack traces from leaking to clients.
    The full exception details are logged server-side for debugging.
    """
    logger = _get_logger()

    # Log full stack trace server-side for debugging
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)

    # Return clean error to client (NO stack trace!)
    error_response = ErrorResponse(
        detail=[
            ErrorDetail(
                msg="An internal server error occurred",
                type="internal_error",
            )
        ],
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(mode="json"),
    )
