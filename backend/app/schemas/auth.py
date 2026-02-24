"""Authentication schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TokenResponse(BaseModel):
    """OAuth2 token response model"""

    model_config = ConfigDict(title="auth.TokenResponse")

    access_token: str
    token_type: str
    expires_in: int
