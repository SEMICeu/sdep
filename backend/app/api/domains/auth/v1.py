"""Auth domain v1 sub-application."""

import json

from fastapi import FastAPI
from fastapi.responses import Response

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common.openapi import create_custom_openapi
from app.api.common.routers import auth
from app.api.common.security import create_verify_bearer_token, get_oauth_schema
from app.config import settings

app_auth_v1 = FastAPI(
    title="SDEP - Auth API",
    description="Authentication endpoints for machine-to-machine OAuth2 Client Credentials flow via Keycloak.",
    version=f"{settings.DTAP}-{settings.IMAGE_TAG}",
    root_path="/api/auth/v1",
    redoc_url=None,
    responses={
        500: {
            "description": "Internal Server Error - an unexpected issue occurred that prevented the request from being completed"
        },
        503: {
            "description": "Service Unavailable - temporarily unable to process requests due to overload, maintenance, or dependency issues (database/authorization server)"
        },
    },
)

app_auth_v1.openapi = create_custom_openapi(app_auth_v1)
register_exception_handlers(app_auth_v1)

app_auth_v1.include_router(auth.router)

oauth2_scheme = get_oauth_schema(auth_version=1)
verify_bearer_token = create_verify_bearer_token(oauth2_scheme)


@app_auth_v1.get("/openapi.json", include_in_schema=False)
async def get_openapi_json():
    return Response(
        content=json.dumps(app_auth_v1.openapi(), indent=2, ensure_ascii=False),
        media_type="application/json",
    )


__all__ = ["app_auth_v1", "verify_bearer_token"]
