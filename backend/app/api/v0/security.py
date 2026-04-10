"""API v0 security configuration and dependencies.

This module provides v0-specific OAuth2 scheme configuration and
authentication dependencies.
"""

from app.api.common.security import create_verify_bearer_token, get_oauth_schema

# OAuth2 scheme for API v0
# This tells Swagger UI to use the OAuth2 Client Credentials flow for M2M authentication
oauth2_scheme_v0 = get_oauth_schema(version_number=0)

# Create v0-specific token verification dependency
verify_bearer_token = create_verify_bearer_token(oauth2_scheme_v0)
