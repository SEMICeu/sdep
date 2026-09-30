"""AMA domain v1 sub-application."""

from app.api.app_factory import create_domain_app
from app.api.common.reference_routers import (
    areas_router,
    competent_authorities_router,
    platforms_router,
)
from app.api.common.security import Role
from app.api.domain_registry import AMA_V1
from app.api.domains.ama.routers import activities_v1

app_ama_v1, verify_bearer_token = create_domain_app(
    AMA_V1,
    [
        activities_v1.router,
        platforms_router("ama", Role.AMA),
        competent_authorities_router("ama", Role.AMA),
        areas_router("ama", Role.AMA),
    ],
)

__all__ = ["app_ama_v1", "verify_bearer_token"]
