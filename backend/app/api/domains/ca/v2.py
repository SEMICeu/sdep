"""CA domain v2 sub-application, including the acknowledged-listings read (random checks)."""

from app.api.app_factory import create_domain_app
from app.api.common.reference_routers import platforms_router
from app.api.common.security import Role
from app.api.domain_registry import CA_V2
from app.api.domains.ca.routers import activities_v2, areas, areas_list_v2, listings_v2

# Platforms only: the own areas are in areas.py, and the competent authority is the caller
app_ca_v2, verify_bearer_token = create_domain_app(
    CA_V2,
    [
        activities_v2.router,
        areas_list_v2.router,
        areas.router,
        listings_v2.router,
        platforms_router("ca", Role.CA),
    ],
)

__all__ = ["app_ca_v2", "verify_bearer_token"]
