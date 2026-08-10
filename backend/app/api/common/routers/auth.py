"""Authentication endpoints using Keycloak."""

import base64
import binascii

import httpx
from fastapi import APIRouter, Form, HTTPException, Request, status

from app.config import settings
from app.exceptions.infrastructure import AuthorizationServerOperationalError
from app.schemas.auth import TokenResponse
from app.schemas.error import ErrorResponse

router = APIRouter(tags=["auth"])


def _build_token_response(response: httpx.Response) -> TokenResponse:
    """Validate Keycloak's HTTP 200 token response and build a ``TokenResponse``.

    A malformed body from Keycloak is an upstream/operational failure (HTTP 503),
    not an SDEP bug (HTTP 500), so each failure mode raises
    ``AuthorizationServerOperationalError`` (mapped to 503 by its registered handler).
    """
    try:
        token_response = response.json()
    except ValueError as e:
        raise AuthorizationServerOperationalError(
            f"Authorization server returned a non-JSON token response: {e!s}"
        ) from e

    if not isinstance(token_response, dict):
        raise AuthorizationServerOperationalError(
            "Authorization server returned a malformed token response"
        )

    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise AuthorizationServerOperationalError(
            "Authorization server returned a token response without an access_token field"
        )

    # expires_in as defined by Keycloak > realm settings > tokens, fallback is 300 seconds
    return TokenResponse(
        access_token=access_token,
        token_type=token_response.get("token_type", "bearer"),
        expires_in=token_response.get("expires_in", 300),
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Get access token (JWT bearer)",
    description="Token endpoint for machine-to-machine authentication using OAuth 2.0 Client Credentials Grant. Supports HTTP Basic Authentication or form parameters (client_id/client_secret), and client-signed JWT (client_id/client_signed_jwt).",
    operation_id="post_auth_token",
    responses={
        "400": {
            "model": ErrorResponse,
            "description": "Bad Request - missing client credentials",
        },
        "401": {
            "model": ErrorResponse,
            "description": "Unauthorized - authentication failed",
        },
    },
)
async def post_auth_token(
    request: Request,
    client_id: str | None = Form(None, description="Client ID for M2M authentication"),
    client_secret: str | None = Form(
        None, description="Client secret for M2M authentication"
    ),
    client_signed_jwt: str | None = Form(
        None, description="Client-signed JWT for M2M authentication"
    ),
    grant_type: str | None = Form(
        None, description="OAuth2 grant type (client_credentials)"
    ),
) -> TokenResponse:
    """Issue a JWT bearer token for M2M authentication by forwarding the request to Keycloak

    Supports three authentication methods:
    1. HTTP Basic Authentication - client_id/client_secret in the Authorization header (RFC 6749)
    2. Form parameters - client_id/client_secret in the request body (RFC 6749)
    3. Client-signed JWT - client_id + client_signed_jwt form parameters (RFC 7523)
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
        except (ValueError, binascii.Error, UnicodeDecodeError):
            # Malformed Basic Auth header → fall back to form parameters.
            # ValueError covers a missing ":" separator in the decoded payload.
            pass

    has_secret_credentials = bool(client_id and client_secret)
    has_partial_secret_credentials = bool(client_id) != bool(client_secret)
    has_client_signed_jwt_credentials = bool(client_signed_jwt)

    if has_secret_credentials and has_client_signed_jwt_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use either client secret credentials or client-signed JWT credentials, not both",
        )

    if has_client_signed_jwt_credentials and not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id is required for client-signed JWT authentication",
        )

    if has_partial_secret_credentials and not has_client_signed_jwt_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client credentials must be provided via HTTP Basic Auth or form parameters",
        )

    if not has_secret_credentials and not has_client_signed_jwt_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client credentials must be provided via HTTP Basic Auth, form parameters, or client-signed JWT",
        )

    if has_secret_credentials and not settings.CLIENT_SECRET_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client secret token authentication is disabled; use client-signed JWT authentication",
        )

    # Check if Keycloak URL is configured
    if not settings.KC_BASE_URL:
        raise AuthorizationServerOperationalError("Keycloak URL is not configured")

    # Prepare the token request payload with client_credentials grant type.
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
    }
    if has_client_signed_jwt_credentials:
        token_data.update(
            {
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_signed_jwt,
            }
        )
    else:
        token_data["client_secret"] = client_secret

    # Construct the full token endpoint URL with realm path
    token_endpoint = (
        f"{settings.KC_BASE_URL.rstrip('/')}/realms/sdep/protocol/openid-connect/token"
    )

    # Forward the request to Keycloak (explicit timeout prevents hung workers if Keycloak is unresponsive)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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

            # Parse and validate the token response (raises 503 on a malformed upstream body)
            return _build_token_response(response)

    except httpx.RequestError as e:
        raise AuthorizationServerOperationalError(
            f"Failed to connect to Keycloak: {e!s}"
        ) from e
