"""Centralized exception handler registration for FastAPI apps."""

from typing import TYPE_CHECKING, cast

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

if TYPE_CHECKING:
    from starlette.types import ExceptionHandler

from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    InvalidTokenError,
    ResourceNotFoundError,
    ValidationError,
)
from app.exceptions.handlers import (
    app_validation_exception_handler,
    authentication_exception_handler,
    authorization_exception_handler,
    business_logic_exception_handler,
    general_exception_handler,
    http_exception_handler,
    resource_not_found_exception_handler,
    validation_exception_handler,
)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers for the application.

    Order matters: more specific handlers should be registered before general ones.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(
        HTTPException, cast("ExceptionHandler", http_exception_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast("ExceptionHandler", validation_exception_handler)
    )
    app.add_exception_handler(
        ValidationError, cast("ExceptionHandler", app_validation_exception_handler)
    )
    app.add_exception_handler(
        BusinessLogicError, cast("ExceptionHandler", business_logic_exception_handler)
    )
    app.add_exception_handler(
        ResourceNotFoundError,
        cast("ExceptionHandler", resource_not_found_exception_handler),
    )
    app.add_exception_handler(
        AuthenticationError, cast("ExceptionHandler", authentication_exception_handler)
    )
    app.add_exception_handler(
        AuthorizationError, cast("ExceptionHandler", authorization_exception_handler)
    )
    app.add_exception_handler(
        InvalidTokenError, cast("ExceptionHandler", authentication_exception_handler)
    )
    app.add_exception_handler(
        Exception, cast("ExceptionHandler", general_exception_handler)
    )


__all__ = ["register_exception_handlers"]
