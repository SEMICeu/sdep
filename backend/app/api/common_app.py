"""Version-independent API endpoints."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common.routers import health, ping
from app.api.domain_registry import API_DOMAINS
from app.config import settings

# Create version-independent sub-application
app_common = FastAPI(
    title="Short Term Rental (STR) - Single Digital Entry Point (SDEP) - Common",
    description="Version-independent endpoints for health monitoring and basic operations.",
    version=f"{settings.DTAP}-{settings.IMAGE_TAG}",
    root_path="/api",
    docs_url=None,
    redoc_url=None,
)

# Register exception handlers for consistent error responses
register_exception_handlers(app_common)

app_common.include_router(health.router)
app_common.include_router(ping.router)


def _render_api_domains() -> str:
    return "\n".join(domain.html for domain in API_DOMAINS)


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
    ul {{ padding-left: 20px; }}
    li {{ margin: 6px 0; }}
    .section {{ margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>SDEP - API Documentation</h1>
  <p>
    Single Digital Entry Point (SDEP) is a gateway for the electronic transmission of data
    between online short-term rental platforms (STR) and competent authorities (CA).
  </p>

  <div class="section">
    <h2>API domains</h2>
{api_domains_html}
  </div>

  <div class="section">
    <h2>Health</h2>
    <ul>
      <li><a href="/api/health">/api/health</a></li>
      <li><a href="/api/ping">/api/ping</a></li>
    </ul>
  </div>

  <div class="section">
    <h2>Contact</h2>
    <p><a href="mailto:nationaalcoordinatorsdep@minbzk.nl">nationaalcoordinatorsdep@minbzk.nl</a></p>
  </div>
</body>
</html>"""
    )


__all__ = ["app_common"]
