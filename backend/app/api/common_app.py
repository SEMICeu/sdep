"""Version-independent API endpoints."""

from fastapi import FastAPI

from app.config import settings

# Create version-independent sub-application
app_common = FastAPI(
    title="Short Term Rental (STR) - Single Digital Entry Point (SDEP) - Common",
    description="Version-independent endpoints for health monitoring and basic operations.",
    version=f"{settings.DTAP}-{settings.IMAGE_TAG}",
    root_path="/api",
)

# Register exception handlers for consistent error responses
from app.api.common.exception_handlers import register_exception_handlers  # noqa: E402

register_exception_handlers(app_common)

# Register health router
from app.api.common.routers import health  # noqa: E402

app_common.include_router(health.router)

__all__ = ["app_common"]
