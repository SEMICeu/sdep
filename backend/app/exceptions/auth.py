"""Authentication and authorization exceptions."""

from .base import SDEPError


class AuthenticationError(SDEPError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(SDEPError):
    """Raised when authorization fails (user authenticated but lacks permissions)."""

    pass


class InvalidTokenError(AuthenticationError):
    """Raised when a token is invalid or expired."""

    pass
