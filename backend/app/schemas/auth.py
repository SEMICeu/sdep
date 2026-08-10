"""Authentication schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    """OAuth 2.0 token response model"""

    model_config = ConfigDict(title="Auth.TokenResponse")

    access_token: str = Field(
        ...,
        description="OAuth 2.0 bearer access token to be used in the Authorization header of subsequent API requests",
    )
    token_type: str = Field(
        ...,
        description="Type of token issued (typically 'Bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Lifetime of the access token in seconds",
    )
