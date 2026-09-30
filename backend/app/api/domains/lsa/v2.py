"""LSA domain v2 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.common.reference_routers import (
    areas_router,
    competent_authorities_router,
    platforms_router,
)
from app.api.common.security import Role
from app.api.domain_registry import LSA_V2
from app.api.domains.lsa.routers import listing_screenings_bulk_v2, listings_v2

app_lsa_v2, verify_bearer_token = create_domain_app(
    LSA_V2,
    [
        listings_v2.router,
        listing_screenings_bulk_v2.router,
        platforms_router("lsa", Role.LSA),
        competent_authorities_router("lsa", Role.LSA),
        areas_router("lsa", Role.LSA),
    ],
)

__all__ = ["app_lsa_v2", "verify_bearer_token"]
