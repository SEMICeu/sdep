"""API configuration for SDEP application.

Each domain is independently versioned as a FastAPI sub-application:
- Auth: mounted at /api/auth/v1 (see app.api.domains.auth.v1)
- CA:   mounted at /api/ca/v1   (see app.api.domains.ca.v1)
- STR:  mounted at /api/str/v1  (see app.api.domains.str.v1)

Common (unversioned):
- Health/ping: mounted at /api (see app.api.common_app)
"""

__all__ = []
