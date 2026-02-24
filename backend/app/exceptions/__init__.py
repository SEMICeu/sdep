"""Custom exceptions for the SDEP application."""

from .auth import AuthenticationError, AuthorizationError, InvalidTokenError
from .base import SDEPError
from .business import (
    ApplicationValidationError,
    DuplicateResourceError,
    InvalidOperationError,
    ResourceNotFoundError,
)
from .infrastructure import (
    AuthorizationServerOperationalError,
    DatabaseOperationalError,
)

__all__ = [
    "ApplicationValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "AuthorizationServerOperationalError",
    "DatabaseOperationalError",
    "DuplicateResourceError",
    "InvalidOperationError",
    "InvalidTokenError",
    "ResourceNotFoundError",
    "SDEPError",
]
