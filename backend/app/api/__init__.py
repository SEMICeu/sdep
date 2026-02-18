"""API configuration for SDEP application.

Versioned APIs are implemented as FastAPI sub-applications:
- v0: mounted at /api/v0 (see app.api.v0)
- v1: mounted at /api/v1 (see app.api.v1)

Common routers shared across API versions:
- Health monitoring (see app.api.common.routers.health)
- Competent Authority (CA) endpoints (see app.api.common.routers.ca)
- Short-Term Rental Platform (STR) endpoints (see app.api.common.routers.str)
"""

__all__ = []
