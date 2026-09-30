"""STA domain v2 sub-application, including the listing endpoints (random checks)."""

from app.api.app_factory import create_domain_app
from app.api.common.reference_routers import (
    areas_router,
    competent_authorities_router,
    platforms_router,
)
from app.api.common.security import Role
from app.api.domain_registry import STA_V2
from app.api.domains.sta.routers import activities_v1, listings_v2

# The activity endpoints are unchanged from v1, so v2 reuses its router
app_sta_v2, verify_bearer_token = create_domain_app(
    STA_V2,
    [
        activities_v1.router,
        listings_v2.router,
        platforms_router("sta", Role.STA),
        competent_authorities_router("sta", Role.STA),
        areas_router("sta", Role.STA),
    ],
)

__all__ = ["app_sta_v2", "verify_bearer_token"]
