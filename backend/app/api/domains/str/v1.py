"""STR domain v1 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.domain_registry import STR_V1
from app.api.domains.str.routers import activities_bulk_v1, areas, areas_list_v1

app_str_v1, verify_bearer_token = create_domain_app(
    STR_V1, [areas_list_v1.router, areas.router, activities_bulk_v1.router]
)

__all__ = ["app_str_v1", "verify_bearer_token"]
