"""CA domain v2 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.domain_registry import CA_V2
from app.api.domains.ca.routers import activities_v2, areas

app_ca_v2, verify_bearer_token = create_domain_app(
    CA_V2, [activities_v2.router, areas.router]
)

__all__ = ["app_ca_v2", "verify_bearer_token"]
