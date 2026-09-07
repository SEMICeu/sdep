"""Version-independent API endpoints."""

import json
from copy import deepcopy
from html import escape
from typing import Any

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, Response

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common.openapi import create_custom_openapi
from app.api.common.routers import health, ping
from app.api.common.security import (
    create_verify_bearer_token,
    get_oauth_schema,
)
from app.api.common.security import (
    verify_bearer_token as _default_verify,
)
from app.api.domain_registry import API_DOMAINS, API_SCOPES, OAS_VERSION
from app.config import settings

# Create version-independent sub-application
app_common = FastAPI(
    title="Short Term Rental (STR) - Single Digital Entry Point (SDEP) - Common",
    description="Version-independent endpoints for health monitoring and basic operations.",
    version=settings.api_version_label,
    root_path="/api",
    docs_url=None,
    redoc_url=None,
)

app_common.openapi = create_custom_openapi(app_common)

# Register exception handlers for consistent error responses
register_exception_handlers(app_common)

app_common.include_router(health.router)
app_common.include_router(ping.router)

# Same bearer-token override the versioned domains use, so the docs pages offer Authorize.
_oauth2_scheme = get_oauth_schema(auth_version=1)
app_common.dependency_overrides[_default_verify] = create_verify_bearer_token(
    _oauth2_scheme
)


def _openapi_for(paths: set[str]) -> dict[str, Any]:
    """Return the common contract narrowed to the given paths.

    The version-independent endpoints have no sub-app of their own (mounting one at
    `/api/ping` would redirect the endpoint itself), so each gets a docs page backed by a
    filtered copy of the shared schema instead.
    """
    schema = deepcopy(app_common.openapi())
    schema["paths"] = {
        path: item for path, item in schema["paths"].items() if path in paths
    }

    return schema


def _register_endpoint_docs(name: str, title: str, paths: set[str]) -> None:
    """Register a Swagger UI page plus its OpenAPI document for one endpoint."""
    docs_path = f"/{name}/docs"
    openapi_path = f"/{name}/openapi.json"

    @app_common.get(openapi_path, include_in_schema=False, name=f"{name}_openapi")
    async def endpoint_openapi(request: Request) -> Response:
        schema = _openapi_for(paths)

        # FastAPI injects this into its own /openapi.json at request time. A custom route
        # must do the same, or Swagger UI resolves `/ping` against the page origin and
        # calls it without the `/api` mount prefix.
        root_path = request.scope.get("root_path", "").rstrip("/")
        if root_path:
            schema["servers"] = [{"url": root_path}]

        return Response(
            content=json.dumps(schema, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    @app_common.get(docs_path, include_in_schema=False, name=f"{name}_docs")
    async def endpoint_docs(request: Request) -> HTMLResponse:
        root_path = request.scope.get("root_path", "").rstrip("/")

        return get_swagger_ui_html(
            openapi_url=f"{root_path}{openapi_path}",
            title=title,
            oauth2_redirect_url=None,
        )


_register_endpoint_docs("ping", f"{app_common.title} - Ping", {"/ping"})


def _render_api_domains() -> str:
    """Render the domains grouped by scope, in API_SCOPES order."""
    blocks: list[str] = []
    for scope, heading, note in API_SCOPES:
        blocks.append(f"    <h3>{escape(heading)}</h3>")
        blocks.append(f'    <p class="scope-note">{escape(note)}</p>')
        blocks.extend(domain.html for domain in API_DOMAINS if domain.scope == scope)

    return "\n".join(blocks)


@app_common.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def docs_landing_page():
    """Landing page linking to versioned API documentation."""
    api_domains_html = _render_api_domains()

    return HTMLResponse(
        content=f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SDEP - API Documentation</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }}
    h1 {{ border-bottom: 2px solid #2563eb; padding-bottom: 8px; }}
    a {{ color: #2563eb; }}
    .version {{ background: #f0f7ff; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 16px 0; }}
    .version a {{ font-weight: bold; font-size: 1.1em; }}
    .status {{ display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 4px; background: #e5e7eb; color: #374151; font-size: 0.85em; font-weight: 600; }}
    .status-stable {{ background: #dcfce7; color: #166534; }}
    .status-beta {{ background: #fef3c7; color: #92400e; }}
    /* Deployment and OAS badges, mirroring the ones Swagger UI shows beside each API title. */
    .badge {{ display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 4px; background: #e5e7eb; color: #374151; font-size: 0.75rem; font-weight: 600; vertical-align: middle; }}
    .badge-oas {{ background: #dcfce7; color: #166534; }}
    ul {{ padding-left: 20px; }}
    li {{ margin: 6px 0; }}
    .section {{ margin-top: 24px; }}
    h3 {{ margin: 20px 0 0; font-size: 1.05em; color: #374151; }}
    .scope-note {{ margin: 0; color: #6b7280; font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>SDEP - API Documentation<span class="badge">{settings.api_version_label}</span><span class="badge badge-oas">OAS {OAS_VERSION}</span></h1>
  <p>
    Single Digital Entry Point (SDEP) is a gateway for the electronic transmission of data
    between online short-term rental platforms (STR) and competent authorities (CA).
  </p>

  <div class="section">
    <h2>API domains</h2>
{api_domains_html}
  </div>

  <div class="section">
    <h2>Common</h2>
    <div class="version">
      <a href="/api/ping/docs">Ping</a>
      <span class="status status-stable">authenticated</span>
      &nbsp;|&nbsp;
      <a href="/api/ping/openapi.json">OpenAPI JSON</a>
    </div>
    <div class="version">
      <a href="/api/health">Health</a>
      <span class="status status-beta">unauthenticated</span>
    </div>
  </div>

  <div class="section">
    <h2>Contact</h2>
    <p><a href="mailto:nationaalcoordinatorsdep@minbzk.nl">nationaalcoordinatorsdep@minbzk.nl</a></p>
  </div>
</body>
</html>"""
    )


__all__ = ["app_common"]
