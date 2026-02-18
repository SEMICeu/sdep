"""API v0 security configuration and dependencies.

This module provides v0-specific OAuth2 scheme configuration and
authentication dependencies.
"""

from fastapi import HTTPException, Request, status
from fastapi.openapi.models import OAuthFlowClientCredentials, OAuthFlows
from fastapi.security import OAuth2
from fastapi.security.utils import get_authorization_scheme_param

from app.api.common.security import create_verify_bearer_token
from app.config import settings


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


# OAuth2 scheme for API v0
# This tells Swagger UI to use the OAuth2 Client Credentials flow for M2M authentication
oauth2_scheme_v0 = OAuth2ClientCredentials(
    flows=OAuthFlows(
        clientCredentials=OAuthFlowClientCredentials(
            tokenUrl=f"{settings.BACKEND_BASE_URL}/api/v0/auth/token",
            scopes={},
        )
    ),
    auto_error=True,
)


# Create v0-specific token verification dependency
verify_bearer_token = create_verify_bearer_token(oauth2_scheme_v0)
