"""Factory for building per-domain FastAPI sub-applications.

Every API domain (CA, STR, REP, ...) builds its sub-application the same way: metadata
from the domain registry, the shared custom OpenAPI generator and exception handlers, the
routers the domain exposes, and the OAuth2 bearer-token security override. This single
factory captures that shared shape so each domain only supplies its registry entry and the
list of routers to mount.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import Response

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common.openapi import create_custom_openapi
from app.api.common.security import (
    create_verify_bearer_token,
    get_oauth_schema,
)
from app.api.common.security import (
    verify_bearer_token as _default_verify,
)
from app.api.domain_registry import ApiDomain
from app.config import settings

OpenApiRoute = Callable[[], Awaitable[Response]]

COMMON_RESPONSES: dict[int | str, dict[str, Any]] = {
    500: {
        "description": "Internal Server Error - an unexpected issue occurred that prevented the request from being completed"
    },
    503: {
        "description": "Service Unavailable - temporarily unable to process requests due to overload, maintenance, or dependency issues (database/authorization server)"
    },
}


def create_domain_app(
    domain: ApiDomain, routers: list[APIRouter]
) -> tuple[FastAPI, Callable[..., Any], OpenApiRoute]:
    app = FastAPI(
        title=domain.title,
        description=domain.description_with_status,
        version=f"{settings.DTAP}-{settings.IMAGE_TAG}",
        root_path=domain.root_path,
        redoc_url=None,
        responses=COMMON_RESPONSES,
    )

    app.openapi = create_custom_openapi(app)
    register_exception_handlers(app)

    for router in routers:
        app.include_router(router)

    oauth2_scheme = get_oauth_schema(auth_version=1)
    verify_bearer_token = create_verify_bearer_token(oauth2_scheme)
    app.dependency_overrides[_default_verify] = verify_bearer_token

    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json():
        return Response(
            content=json.dumps(app.openapi(), indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    return app, verify_bearer_token, get_openapi_json
