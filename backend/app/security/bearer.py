"""Security utilities and dependencies (backwards compatibility wrapper).

This module maintains backwards compatibility by importing from the v0 security module.
Common routers that are shared between API versions will use this import.

For version-specific functionality, import from:
- app.api.v0.security for v0-specific security
- app.api.v1.security for v1-specific security
- app.api.common.security for version-agnostic JWT validation
"""

# Import v0 security for backwards compatibility with existing common routers
# Common routers (ping, str, ca) use this import and are included in both v0 and v1
# Re-export common security utilities for direct access
from app.api.common.security import (
    create_verify_bearer_token,
    get_keycloak_public_key,
    validate_jwt_token,
)
from app.api.v0.security import (
    oauth2_scheme_v0 as oauth2_scheme,
)
from app.api.v0.security import (
    verify_bearer_token,
)

__all__ = [
    "create_verify_bearer_token",
    "get_keycloak_public_key",
    "oauth2_scheme",
    "validate_jwt_token",
    "verify_bearer_token",
]
