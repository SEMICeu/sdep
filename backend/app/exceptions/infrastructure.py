"""Infrastructure-level exceptions for external dependency failures."""

from .base import SDEPError


class DatabaseOperationalError(SDEPError):
    """Raised when the database is temporarily unavailable or unreachable."""

    pass


class AuthorizationServerOperationalError(SDEPError):
    """Raised when the authorization server (Keycloak) is temporarily unavailable or unreachable."""

    pass


class MalwareScannerOperationalError(SDEPError):
    """Raised when the malware scanner (ClamAV) cannot complete a scan."""

    pass
