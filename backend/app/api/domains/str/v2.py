"""STR domain v2 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.domain_registry import STR_V2
from app.api.domains.str.routers import activities_bulk_v2, areas, areas_list_v2

app_str_v2, verify_bearer_token = create_domain_app(
    STR_V2, [areas_list_v2.router, areas.router, activities_bulk_v2.router]
)

__all__ = ["app_str_v2", "verify_bearer_token"]
