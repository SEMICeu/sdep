"""REP domain v1 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.domain_registry import REP_V1
from app.api.domains.rep.routers import activities_v1

app_rep_v1, verify_bearer_token, get_openapi_json = create_domain_app(
    REP_V1, [activities_v1.router]
)

__all__ = ["app_rep_v1", "get_openapi_json", "verify_bearer_token"]
