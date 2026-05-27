"""Common security utilities for JWT token validation.

This module provides version-agnostic JWT validation logic that can be reused
across different API versions (v1, v2, etc.).
"""

import threading
from collections.abc import Callable
from enum import StrEnum
from typing import Any

# PyJWT replaces python-jose (unmaintained since 2022, CVE-2024-33663 algorithm confusion)
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.openapi.models import OAuthFlowClientCredentials, OAuthFlows
from fastapi.security import OAuth2
from fastapi.security.utils import get_authorization_scheme_param
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidTokenError,
    PyJWKClient,
)

from app.config import settings
from app.exceptions.infrastructure import AuthorizationServerOperationalError

# JWKS client with built-in caching (TTL 300s = 5 min, supports key rotation)
_jwks_client: PyJWKClient | None = None
_jwks_client_lock = threading.Lock()

JWKS_CACHE_TTL = 300


class Role(StrEnum):
    """Keycloak realm roles for SDEP authorization."""

    CA = "sdep_ca"
    STR = "sdep_str"
    READ = "sdep_read"
    WRITE = "sdep_write"


def _get_jwks_client() -> PyJWKClient:
    """Get or create the JWKS client (thread-safe, lazy init)."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    with _jwks_client_lock:
        if _jwks_client is not None:
            return _jwks_client

        if not settings.KC_BASE_URL:
            raise AuthorizationServerOperationalError("Keycloak URL is not configured")

        certs_url = f"{settings.KC_BASE_URL.rstrip('/')}/realms/sdep/protocol/openid-connect/certs"

        try:
            _jwks_client = PyJWKClient(
                certs_url,
                cache_jwk_set=True,
                lifespan=JWKS_CACHE_TTL,
            )
        except Exception as e:
            raise AuthorizationServerOperationalError(
                f"Failed to initialize JWKS client: {e!s}"
            ) from e

        return _jwks_client


def validate_jwt_token(token: str) -> dict[str, Any]:
    """Validate and decode a JWT token using Keycloak public keys.

    This is a version-agnostic function that can be used by any API version.

    Args:
        token: JWT bearer token string

    Returns:
        Decoded JWT payload containing user/client information

    Raises:
        HTTPException: If token is invalid, expired, or has invalid claims
    """
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)

        # Audience verification is disabled: Keycloak client credentials tokens do not
        # include an "aud" claim by default, and enforcing it would reject all current clients.
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except InvalidAudienceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (DecodeError, InvalidTokenError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def create_verify_bearer_token(
    oauth2_scheme: OAuth2,
) -> Callable:
    """Factory function to create version-specific token verification dependency.

    Args:
        oauth2_scheme: Version-specific OAuth2 scheme

    Returns:
        Async function that verifies JWT bearer tokens
    """

    async def verify_bearer_token(
        request: Request,
        token: str = Depends(oauth2_scheme),
    ) -> dict[str, Any]:
        """Verify JWT bearer token using the configured OAuth2 scheme.

        Args:
            request: FastAPI request — used to stash the parsed payload on
                ``request.state`` so the audit middleware can reuse it instead
                of re-running JWT signature verification.
            token: JWT Bearer token from OAuth2 flow

        Returns:
            Decoded JWT payload

        Raises:
            HTTPException: If token is invalid
        """
        payload = validate_jwt_token(token)
        request.state.jwt_payload = payload
        return payload

    return verify_bearer_token


class OAuth2ClientCredentials(OAuth2):
    """OAuth2 Client Credentials flow with token extraction from Authorization header.

    This extends FastAPI's OAuth2 base class to support extracting Bearer tokens
    from the Authorization header for the Client Credentials flow.
    """

    async def __call__(self, request: Request) -> str | None:
        """Extract Bearer token from Authorization header.

        Args:
            request: FastAPI request object

        Returns:
            The Bearer token string

        Raises:
            HTTPException: If token is missing or invalid format
        """
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)

        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None

        return param


def get_oauth_schema(auth_version: int = 1):
    return OAuth2ClientCredentials(
        flows=OAuthFlows(
            clientCredentials=OAuthFlowClientCredentials(
                tokenUrl=f"{settings.BACKEND_BASE_URL}/api/auth/v{auth_version}/token",
                scopes={},
            )
        ),
        auto_error=True,
    )


# Default OAuth2 scheme and bearer token verifier for use by auth_dependencies
_default_oauth2_scheme = get_oauth_schema(auth_version=1)
verify_bearer_token = create_verify_bearer_token(_default_oauth2_scheme)
