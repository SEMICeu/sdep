"""CA domain v1 sub-application."""

from app.api.domains.ca.app_factory import create_ca_app
from app.api.domains.ca.routers import activities_v1

app_ca_v1, verify_bearer_token, get_openapi_json = create_ca_app(
    1, activities_v1.router, status="stable"
)

__all__ = ["app_ca_v1", "get_openapi_json", "verify_bearer_token"]
