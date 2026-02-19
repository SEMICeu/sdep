"""Common security utilities for JWT token validation.

This module provides version-agnostic JWT validation logic that can be reused
across different API versions (v0, v1, etc.).
"""

from collections.abc import Callable
from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from app.config import settings


@lru_cache(maxsize=1)
def get_keycloak_public_key() -> dict[str, Any]:
    """Fetch Keycloak public key for JWT validation.

    Cached to avoid repeated network calls.

    Returns:
        JWKS (JSON Web Key Set) dictionary

    Raises:
        HTTPException: If unable to fetch public key
    """
    if not settings.KC_BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keycloak URL is not configured",
        )

    # Construct the certs endpoint URL
    certs_url = (
        f"{settings.KC_BASE_URL.rstrip('/')}/realms/sdep/protocol/openid-connect/certs"
    )

    try:
        response = httpx.get(certs_url, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Keycloak public key: {e!s}",
        ) from e


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
        # Get Keycloak public keys
        jwks = get_keycloak_public_key()

        # Decode and validate the token
        # The library selects the correct key from JWKS automatically
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience="account",  # Keycloak default audience
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
            },
        )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTClaimsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTError as e:
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
        token: str = Depends(oauth2_scheme),
    ) -> dict[str, Any]:
        """Verify JWT bearer token using the configured OAuth2 scheme.

        Args:
            token: JWT Bearer token from OAuth2 flow

        Returns:
            Decoded JWT payload

        Raises:
            HTTPException: If token is invalid
        """
        return validate_jwt_token(token)

    return verify_bearer_token
