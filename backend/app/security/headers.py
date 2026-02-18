"""Security headers middleware for FastAPI application."""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
        enable_csp: bool = False,  # Disable by default if handled by Nginx
        csp_policy: str | None = None,
    ):
        """
        Initialize security headers middleware.

        Args:
            app: The ASGI application
            enable_hsts: Enable Strict-Transport-Security header
            hsts_max_age: Max age for HSTS in seconds (default: 1 year)
            enable_csp: Enable Content-Security-Policy (disable if Nginx handles it)
            csp_policy: Custom CSP policy string
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.enable_csp = enable_csp
        self.csp_policy = csp_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # MIME-sniffing protection
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Referrer policy - prevent information leakage
        response.headers["Referrer-Policy"] = "no-referrer"

        # Permissions policy - restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=(), "
            "speaker=(self)"
        )

        # Cross-Origin-Opener-Policy - isolate browsing context
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # Cross-Origin-Resource-Policy - prevent cross-origin loading
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # Cross-Origin-Embedder-Policy - Use unsafe-none for compatibility
        # Note: require-corp is too strict and can cause 504/connectivity issues in K8s
        response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"

        # Cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"

        # HSTS - enforce HTTPS (optional, usually handled by reverse proxy)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Content-Security-Policy (optional, usually handled by Nginx)
        if self.enable_csp and self.csp_policy:
            response.headers["Content-Security-Policy"] = self.csp_policy

        return response

    def _is_sensitive_endpoint(self, path: str) -> bool:
        """
        Determine if an endpoint should have strict cache control.

        Args:
            path: The request path

        Returns:
            True if endpoint is sensitive and should not be cached
        """
        sensitive_patterns = [
            "/api/auth/",
            "/api/v0/auth/",
            "/api/v0/activities",
            "/api/v0/areas",
            "/api/v0/competent-authority",
            "/api/v0/openapi.json",
        ]
        return any(path.startswith(pattern) for pattern in sensitive_patterns)


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
