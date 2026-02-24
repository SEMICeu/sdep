"""API v0 sub-application implementation."""

import json

from fastapi import FastAPI
from fastapi.responses import Response

from app.api.common.openapi import create_custom_openapi
from app.config import settings

# Create sub-application (v0)
app_v0 = FastAPI(
    title="Short Term Rental (STR) - Single Digital Entry Point (SDEP)",
    description="SDEP is a gateway for the electronic transmission of data between online short-term rental platforms (STR) and competent authorities (CA), ensuring timely, reliable and efficient data sharing processes.\n\n- [Github (open source)](https://github.com/SEMICeu/sdep)\n\n- [EU legislation](https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng)\n\n- [STR Application Profile (STR-AP)](https://semiceu.github.io/STR-AP/releases/1.0.1/)\n\n- [STR prototype v0.0.65](https://eu-str.sdep-pilot.eu/swagger/index.html)\n\nContact:\n\n- [boris.dijkmans@rijksoverheid.nl](mailto:boris.dijkmans@rijksoverheid.nl)",
    version=f"{settings.DTAP}-{settings.IMAGE_TAG}",
    root_path="/api/v0",
    responses={
        500: {
            "description": "Internal Server Error - an unexpected issue occurred that prevented the request from being completed"
        },
        503: {
            "description": "Service Unavailable - temporarily unable to process requests due to overload, maintenance, or dependency issues (database/authorization server)"
        },
    },
)

# Override openapi method to apply custom modifications (alphabetical sorting)
app_v0.openapi = create_custom_openapi(app_v0)

# Register exception handlers for app_v0
# This is needed for tests that use app_v0 directly
from app.api.common.exception_handlers import register_exception_handlers

register_exception_handlers(app_v0)

# Register routers from common
from app.api.common.routers import (
    auth,
    ca_activities,
    ca_areas,
    health,
    ping,
    str_activities,
    str_areas,
)

# Sort alphabetically
app_v0.include_router(auth.router, prefix="/auth")
app_v0.include_router(ca_activities.router, prefix="")
app_v0.include_router(ca_areas.router, prefix="")
app_v0.include_router(health.router, prefix="")
app_v0.include_router(ping.router, prefix="")
app_v0.include_router(str_activities.router, prefix="")
app_v0.include_router(str_areas.router, prefix="")


# Custom OpenAPI endpoint with pretty-printed JSON
@app_v0.get("/openapi.json", include_in_schema=False)
async def get_openapi_json():
    """Return the OpenAPI schema as pretty-printed JSON."""
    return Response(
        content=json.dumps(app_v0.openapi(), indent=2, ensure_ascii=False),
        media_type="application/json",
    )


__all__ = ["app_v0"]
