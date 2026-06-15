"""STR domain v1 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.common.routers import str_activities_bulk, str_areas
from app.api.domain_registry import STR_V1

app_str_v1, verify_bearer_token, get_openapi_json = create_domain_app(
    STR_V1, [str_areas.router, str_activities_bulk.router]
)

__all__ = ["app_str_v1", "get_openapi_json", "verify_bearer_token"]
