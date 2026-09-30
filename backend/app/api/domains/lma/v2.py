"""LMA domain v2 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.common.reference_routers import (
    areas_router,
    competent_authorities_router,
    platforms_router,
)
from app.api.common.security import Role
from app.api.domain_registry import LMA_V2
from app.api.domains.lma.routers import listings_v2

app_lma_v2, verify_bearer_token = create_domain_app(
    LMA_V2,
    [
        listings_v2.router,
        platforms_router("lma", Role.LMA),
        competent_authorities_router("lma", Role.LMA),
        areas_router("lma", Role.LMA),
    ],
)

__all__ = ["app_lma_v2", "verify_bearer_token"]
