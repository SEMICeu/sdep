"""Security headers middleware for FastAPI application."""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.api.domain_registry import API_DOMAINS

# Every domain gets no-cache headers, e.g. "/api/str/" for "/api/str/v2".
SENSITIVE_PREFIXES = tuple(
    sorted({domain.root_path.rsplit("/", 1)[0] + "/" for domain in API_DOMAINS})
)
# Swagger UI pages get the relaxed docs CSP: every domain version, plus ping.
SWAGGER_DOCS_PATHS = frozenset(
    {"/api/ping/docs"} | {domain.docs_path for domain in API_DOMAINS}
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add comprehensive security headers to all responses.

    This middleware implements OWASP recommended security headers to protect
    against common web vulnerabilities including:
    - Clickjacking attacks (X-Frame-Options, CSP frame-ancestors)
    - MIME-sniffing attacks (X-Content-Type-Options)
    - Information leakage (Referrer-Policy)
    - Cross-origin attacks (COOP, CORP, COEP)
    - Unauthorized feature access (Permissions-Policy)
    - XSS attacks (Content-Security-Policy)
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,
        enable_csp: bool = False,
        csp_policy: str | None = None,
        csp_policy_landing: str | None = None,
        csp_policy_docs: str | None = None,
        api_version: str | None = None,
    ):
        super().__init__(app)
        self.api_version = api_version
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.enable_csp = enable_csp
        self.csp_policy = csp_policy
        self.csp_policy_landing = csp_policy_landing
        self.csp_policy_docs = csp_policy_docs

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Full semantic version of the release on every response (NLgov
        # `/core/version-header`); the contract major stays in the path.
        if self.api_version:
            response.headers["API-Version"] = self.api_version

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # MIME-sniffing protection
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Referrer policy - prevent information leakage
        response.headers["Referrer-Policy"] = "no-referrer"

        # Permissions policy - restrict browser features.
        # Note: "speaker" is not a registered Permissions-Policy feature and is
        # silently ignored by browsers. The (now obsolete) "Speaker API" was
        # never standardized; current audio-output control is governed by
        # getUserMedia and "speaker-selection" (still experimental, limited
        # implementation), neither of which we need to expose. Listing it would
        # only mislead readers into thinking the header gates speaker access.
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # COOP (Cross-Origin-Opener-Policy) - isolate browsing context so a
        # cross-origin window cannot script this document via window.opener
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # CORP (Cross-Origin-Resource-Policy) - prevent other origins from
        # loading our responses as <script>, <img>, fetch(), etc.
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        # Cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"

        # HSTS - enforce HTTPS. Enabled by this application as defense in depth;
        # the reverse proxy in front of it may set the header as well.
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Content-Security-Policy — route-specific to keep the strict policy
        # on paths that internet.nl tests (root, API endpoints) while allowing
        # 'unsafe-inline' only on Swagger UI docs pages that require it.
        if self.enable_csp:
            path = request.url.path
            if self._is_swagger_docs_endpoint(path):
                policy = self.csp_policy_docs
            elif self._is_docs_landing_endpoint(path):
                policy = self.csp_policy_landing
            else:
                policy = self.csp_policy
            if policy:
                response.headers["Content-Security-Policy"] = policy

        return response

    def _is_sensitive_endpoint(self, path: str) -> bool:
        return path.startswith(SENSITIVE_PREFIXES)

    def _is_swagger_docs_endpoint(self, path: str) -> bool:
        return path in SWAGGER_DOCS_PATHS

    def _is_docs_landing_endpoint(self, path: str) -> bool:
        return path == "/api/docs"


class ApiSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Lightweight security headers middleware specifically for API endpoints.

    Use this version if you want minimal overhead and Nginx handles most security.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add essential API security headers."""
        response = await call_next(request)

        # Only add headers to API endpoints
        if request.url.path.startswith("/api/"):
            # Prevent caching of API responses
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )
            response.headers["Pragma"] = "no-cache"

            # Additional API-specific headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"

        return response
