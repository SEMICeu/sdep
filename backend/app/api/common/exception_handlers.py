"""Centralized exception handler registration for FastAPI apps."""

from typing import TYPE_CHECKING, cast

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

if TYPE_CHECKING:
    from starlette.types import ExceptionHandler

from app.exceptions import (
    ApplicationValidationError,
    AuthenticationError,
    AuthorizationError,
    AuthorizationServerOperationalError,
    DatabaseOperationalError,
    InvalidTokenError,
    ResourceNotFoundError,
)
from app.exceptions.handlers import (
    authentication_exception_handler,
    authorization_exception_handler,
    authorization_server_unavailable_exception_handler,
    business_logic_exception_handler,
    database_unavailable_exception_handler,
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
        ApplicationValidationError,
        cast("ExceptionHandler", business_logic_exception_handler),
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
        DatabaseOperationalError,
        cast("ExceptionHandler", database_unavailable_exception_handler),
    )
    # SQLAlchemy raises OperationalError natively (e.g. DB unreachable). Without this
    # registration it would match the Exception catch-all via MRO and return 500.
    app.add_exception_handler(
        SQLAlchemyOperationalError,
        cast("ExceptionHandler", database_unavailable_exception_handler),
    )
    app.add_exception_handler(
        AuthorizationServerOperationalError,
        cast("ExceptionHandler", authorization_server_unavailable_exception_handler),
    )
    app.add_exception_handler(
        Exception, cast("ExceptionHandler", general_exception_handler)
    )


__all__ = ["register_exception_handlers"]
