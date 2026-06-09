"""Single Digital Entrypoint"""

import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common_app import app_common
from app.api.domain_registry import AUTH_V1, CA_V1, CA_V2, STR_V1
from app.api.domains.auth.v1 import app_auth_v1
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.str.v1 import app_str_v1
from app.config import settings
from app.db.config import async_engine
from app.security import AuditLogMiddleware, SecurityHeadersMiddleware
from app.security.audit_retention import audit_log_cleanup_loop

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
app = FastAPI(lifespan=lifespan)

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================
# Register exception handlers for consistent error responses
register_exception_handlers(app)

# ============================================================================
# MIDDLEWARE
# ============================================================================
# Add security headers middleware for OWASP compliance
# This provides defense-in-depth against XSS, clickjacking, and other attacks
#
# CSP Policy explanation:
# - default-src 'self': Only load resources from same origin
# - script-src: Allow same-origin scripts + inline + CDN for Swagger UI
# - style-src: Allow same-origin styles + inline + CDN for Swagger UI
# - img-src 'self' data:: Allow images from same origin and data URIs
# - font-src: Allow fonts from CDN (for Swagger UI)
# - connect-src 'self': Allow API calls to same origin
# - frame-ancestors 'none': Prevent framing (clickjacking protection)
# - base-uri 'self': Restrict <base> tag URLs
# - object-src 'none': Block <object>, <embed>, <applet>
# - form-action 'self': Restrict form submission targets
# Add audit log middleware for request tracking
# Starlette LIFO: last added = outermost = runs first
# AuditLogMiddleware runs after SecurityHeadersMiddleware (added after = runs inside)
app.add_middleware(AuditLogMiddleware)

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
)

# ============================================================================
# MOUNT SUB-APPLICATIONS
# ============================================================================

# Mount domain sub-applications (most specific paths first)
app.mount(AUTH_V1.root_path, app_auth_v1)
app.mount(CA_V1.root_path, app_ca_v1)
app.mount(CA_V2.root_path, app_ca_v2)
app.mount(STR_V1.root_path, app_str_v1)

# Mount version-independent sub-application last (broader path)
app.mount("/api", app_common)


@app.get("/")
async def root():
    return "OK"
