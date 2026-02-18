"""Authentication schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    """OAuth2 token request model for form data"""

    model_config = ConfigDict(title="auth.TokenRequest")

    client_id: str | None = Field(
        None,
        description="Client ID for M2M authentication",
        examples=["sdep-m2m-client"],
    )
    client_secret: str | None = Field(
        None,
        description="Client secret for M2M authentication",
        examples=["your-client-secret"],
    )
    grant_type: str | None = Field(
        None,
        description="OAuth2 grant type (client_credentials)",
        examples=["client_credentials"],
    )


class TokenResponse(BaseModel):
    """OAuth2 token response model"""

    model_config = ConfigDict(title="auth.TokenResponse")

    access_token: str
    token_type: str
    expires_in: int


class UnauthorizedError(BaseModel):
    """Unauthorized error response schema"""

    model_config = ConfigDict(title="auth.UnauthorizedError")

    message: str | None = Field(
        None,
        description="Error message for unauthorized access",
        examples=["JWT is invalid"],
    )
