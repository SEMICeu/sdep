"""CA domain v1 sub-application."""

from app.api.domain_registry import CA_V1
from app.api.domains.ca.app_factory import create_ca_app
from app.api.domains.ca.routers import activities_v1

app_ca_v1, verify_bearer_token, get_openapi_json = create_ca_app(
    CA_V1, activities_v1.router
)

__all__ = ["app_ca_v1", "get_openapi_json", "verify_bearer_token"]
