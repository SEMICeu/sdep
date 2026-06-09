"""STR domain v1 sub-application."""

from app.api.common.routers import str_activities_bulk, str_areas
from app.api.domains.str.app_factory import create_str_app

app_str_v1, verify_bearer_token, get_openapi_json = create_str_app(
    1, [str_areas.router, str_activities_bulk.router], status="stable"
)

__all__ = ["app_str_v1", "get_openapi_json", "verify_bearer_token"]
