"""Single Digital Entrypoint"""

from fastapi import FastAPI

from app.api.common.exception_handlers import register_exception_handlers
from app.api.common_app import app_common
from app.api.v0 import app_v0
from app.security import SecurityHeadersMiddleware

# Create FastAPI application instance
app = FastAPI()

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
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_csp=True,
    csp_policy=(
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
    enable_hsts=False,  # Handled by Nginx in production
)

# ============================================================================
# MOUNT SUB-APPLICATIONS
# ============================================================================

# Mount versioned sub-applications first (more specific paths)
app.mount("/api/v0", app_v0)

# Mount version-independent sub-application last (broader path)
app.mount("/api", app_common)


@app.get("/")
async def root():
    return "OK"
