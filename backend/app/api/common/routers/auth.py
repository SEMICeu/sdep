"""Authentication endpoints using Keycloak."""

import base64

import httpx
from fastapi import APIRouter, Form, HTTPException, Request, status

from app.config import settings
from app.schemas.auth import TokenResponse

router = APIRouter(tags=["auth"])


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Get access token (JWT bearer)",
    description="Token endpoint for machine-to-machine authentication using OAuth 2.0 Client Credentials Grant. Supports both HTTP Basic Authentication and form parameters",
    operation_id="post_auth_token",
)
async def post_auth_token(
    request: Request,
    client_id: str | None = Form(None, description="Client ID for M2M authentication"),
    client_secret: str | None = Form(
        None, description="Client secret for M2M authentication"
    ),
    grant_type: str | None = Form(
        None, description="OAuth2 grant type (client_credentials)"
    ),
) -> TokenResponse:
    """Issue a JWT bearer token for M2M authentication by forwarding the request to Keycloak

    Supports two authentication methods per RFC 6749:
    1. HTTP Basic Authentication (Authorization header)
    2. Form parameters (client_id and client_secret in request body)
    """

    # Try to extract credentials from Basic Auth header first
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            # Decode Basic Auth credentials
            encoded_credentials = auth_header[6:]  # Remove "Basic " prefix
            decoded = base64.b64decode(encoded_credentials).decode("utf-8")
            basic_client_id, basic_client_secret = decoded.split(":", 1)

            # Use Basic Auth credentials if form parameters not provided
            if not client_id:
                client_id = basic_client_id
            if not client_secret:
                client_secret = basic_client_secret
        except Exception:
            # If Basic Auth parsing fails, continue with form parameters
            pass

    # Validate that we have credentials from either source
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client credentials must be provided via HTTP Basic Auth or form parameters",
        )
    # Check if Keycloak URL is configured
    if not settings.KC_BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keycloak URL is not configured",
        )

    # Prepare the token request payload with client_credentials grant type
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    # Construct the full token endpoint URL with realm path
    token_endpoint = (
        f"{settings.KC_BASE_URL.rstrip('/')}/realms/sdep/protocol/openid-connect/token"
    )

    # Forward the request to Keycloak
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_endpoint,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Handle Keycloak errors
            if response.status_code != 200:
                error_detail = "Authentication failed"
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error_description", error_detail)
                except Exception:
                    pass

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_detail,
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Parse and return the token response (expires_in as defined by Keycloak > realm settings > tokens, fallback is 300 seconds)
            token_response = response.json()
            return TokenResponse(
                access_token=token_response["access_token"],
                token_type=token_response.get("token_type", "bearer"),
                expires_in=token_response.get("expires_in", 300),
            )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Keycloak: {e!s}",
        ) from e
