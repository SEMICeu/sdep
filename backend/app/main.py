"""Single Digital Entry Point"""

import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common_app import app_common
from app.api.domain_registry import (
    AMA_V1,
    AUTH_V1,
    CA_V1,
    CA_V2,
    LMA_V2,
    LSA_V2,
    STA_V1,
    STA_V2,
    STR_V1,
    STR_V2,
    ApiDomain,
    is_served,
)
from app.api.domains.ama.v1 import app_ama_v1
from app.api.domains.auth.v1 import app_auth_v1
from app.api.domains.ca.routers.areas import MAX_REQUEST_SIZE
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.lma.v2 import app_lma_v2
from app.api.domains.lsa.v2 import app_lsa_v2
from app.api.domains.sta.v1 import app_sta_v1
from app.api.domains.sta.v2 import app_sta_v2
from app.api.domains.str.v1 import app_str_v1
from app.api.domains.str.v2 import app_str_v2
from app.config import settings
from app.db.config import async_engine
from app.security import AuditLogMiddleware, SecurityHeadersMiddleware
from app.security.audit_retention import audit_log_cleanup_loop
from app.security.upload_size import UploadSizeLimitMiddleware

# Configure dedicated audit logger - message-only formatter so JSON lines are clean
_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.INFO)
_audit_handler = logging.StreamHandler(sys.stdout)
_audit_handler.setFormatter(logging.Formatter("%(message)s"))
_audit_logger.addHandler(_audit_handler)
_audit_logger.propagate = False


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage background tasks tied to the application lifecycle.

    On shutdown (e.g. SIGTERM from Kubernetes during HPA scale-down):
    1. Cancel background tasks (audit log cleanup loop)
    2. Dispose the SQLAlchemy async engine - this closes all pooled database
       connections gracefully, so the process can exit with code 0 instead of
       being killed by SIGKILL after terminationGracePeriodSeconds.
    """
    task = asyncio.create_task(audit_log_cleanup_loop(settings.AUDITLOG_RETENTION))
    yield
    # --- Graceful shutdown (e.g. on external SIGTERM) ---
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    # Close all pooled database connections so asyncpg doesn't complain
    # about abandoned connections on process exit.
    await async_engine.dispose()


# Create FastAPI application instance
app = FastAPI(lifespan=lifespan, redirect_slashes=False)

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================
# Register exception handlers for consistent error responses
register_exception_handlers(app)

# ============================================================================
# MIDDLEWARE
# ============================================================================
# Upload size limit for the area upload (1 MiB file plus multipart envelope), checked
# before the body is parsed. Added first, so it runs innermost: its 413 still gets
# the security headers and the audit log.
app.add_middleware(
    UploadSizeLimitMiddleware,
    max_bytes=MAX_REQUEST_SIZE,
    path_pattern=r"/api/ca/v[0-9]+/areas",
)

# Add audit log middleware for request tracking
# Starlette LIFO: last added = outermost = runs first
# AuditLogMiddleware runs after SecurityHeadersMiddleware (added after = runs inside)
app.add_middleware(AuditLogMiddleware)

# Security headers (OWASP), with one CSP per kind of page:
# - Main (API responses): strict, same origin only ('self')
# - Landing page (/api/docs): adds inline styles
# - Swagger UI pages: add inline scripts/styles and the jsdelivr CDN (Swagger UI assets)
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_csp=True,
    csp_policy=(
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "form-action 'self'"
    ),
    csp_policy_landing=(
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "form-action 'self'"
    ),
    csp_policy_docs=(
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "form-action 'self'"
    ),
    enable_hsts=True,
    api_version=settings.api_version,
)

# ============================================================================
# MOUNT SUB-APPLICATIONS
# ============================================================================

# Every domain version with its sub-app, in mount order (most specific paths first).
DOMAIN_APPS: tuple[tuple[ApiDomain, FastAPI], ...] = (
    (AUTH_V1, app_auth_v1),
    (CA_V1, app_ca_v1),
    (CA_V2, app_ca_v2),
    (STR_V1, app_str_v1),
    (STR_V2, app_str_v2),
    (LSA_V2, app_lsa_v2),
    (LMA_V2, app_lma_v2),
    (AMA_V1, app_ama_v1),
    (STA_V1, app_sta_v1),
    (STA_V2, app_sta_v2),
)


def mount_domain_apps(root_app: FastAPI) -> None:
    """Mount the served versions only: an unserved (alpha) version is a plain 404.

    See is_served() in app/api/domain_registry.py.
    """
    for domain, domain_app in DOMAIN_APPS:
        if is_served(domain):
            root_app.mount(domain.root_path, domain_app)


mount_domain_apps(app)

# Mount version-independent sub-application last (broader path)
app.mount("/api", app_common)


@app.get("/")
async def root():
    return "OK"
