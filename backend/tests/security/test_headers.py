"""Tests for security headers middleware.

Tests XSS protection, output encoding, and OWASP security headers compliance.
"""

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
class TestSecurityHeadersMiddleware:
    """Test suite for SecurityHeadersMiddleware."""

    async def test_root_endpoint_has_basic_headers(self):
        """Test that root endpoint has basic security headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

            # Basic security headers should be present on all responses
            assert response.status_code == 200
            assert "X-Frame-Options" in response.headers
            assert "X-Content-Type-Options" in response.headers

    async def test_api_endpoint_has_comprehensive_headers(self):
        """Test that API endpoints have comprehensive security headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Use /api/v0/ping - expect 401 but headers should be present
            response = await client.get("/api/v0/ping")

            # CSP - XSS and output encoding protection
            assert "Content-Security-Policy" in response.headers
            csp = response.headers["Content-Security-Policy"]
            assert "default-src 'self'" in csp
            assert "script-src" in csp
            assert "style-src" in csp
            assert "frame-ancestors 'none'" in csp

            # Clickjacking protection
            assert response.headers["X-Frame-Options"] == "DENY"

            # MIME-sniffing protection (XSS prevention)
            assert response.headers["X-Content-Type-Options"] == "nosniff"

            # Information leakage prevention
            assert response.headers["Referrer-Policy"] == "no-referrer"

            # Cross-origin protections
            assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
            assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
            assert response.headers["Cross-Origin-Embedder-Policy"] == "unsafe-none"

            # Permissions policy
            assert "Permissions-Policy" in response.headers
            permissions = response.headers["Permissions-Policy"]
            assert "geolocation=()" in permissions
            assert "microphone=()" in permissions
            assert "camera=()" in permissions

    async def test_csp_allows_swagger_ui_cdn(self):
        """Test that CSP policy allows Swagger UI CDN resources."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should allow cdn.jsdelivr.net for Swagger UI
            assert "https://cdn.jsdelivr.net" in csp
            assert "script-src" in csp and "cdn.jsdelivr.net" in csp
            assert "style-src" in csp and "cdn.jsdelivr.net" in csp
            assert "font-src" in csp

    async def test_csp_blocks_unsafe_eval(self):
        """Test that CSP does not allow unsafe-eval (XSS protection)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should NOT contain unsafe-eval (blocks eval-based XSS)
            assert "'unsafe-eval'" not in csp

    async def test_csp_restricts_object_sources(self):
        """Test that CSP blocks object/embed tags (XSS protection)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should block object/embed
            assert "object-src 'none'" in csp

    async def test_csp_prevents_framing(self):
        """Test that CSP prevents framing (clickjacking protection)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should prevent framing
            assert "frame-ancestors 'none'" in csp

    async def test_sensitive_endpoint_auth(self):
        """Test that sensitive auth endpoints get cache control headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Auth endpoint is sensitive - should have no-cache
            response = await client.post(
                "/api/v0/auth/token",
                data={"username": "test", "password": "test"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Check cache control for sensitive endpoint
            if "/api/v0/auth/" in "/api/v0/auth/token":
                cache_control = response.headers.get("Cache-Control", "")
                # Should have strict cache control
                assert "no-store" in cache_control or "no-cache" in cache_control

    async def test_sensitive_endpoint_openapi(self):
        """Test that OpenAPI schema endpoint gets cache control headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/openapi.json")

            # OpenAPI is marked as sensitive
            cache_control = response.headers.get("Cache-Control", "")
            assert "no-store" in cache_control or "no-cache" in cache_control
            assert response.headers.get("Pragma") == "no-cache"

    async def test_hsts_disabled_by_default(self):
        """Test that HSTS is disabled (handled by Nginx in production)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            # HSTS should not be present (handled by reverse proxy)
            assert "Strict-Transport-Security" not in response.headers

    async def test_all_api_endpoints_have_headers(self):
        """Test that all API endpoints receive security headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            endpoints = [
                "/api/v0/ping",
                "/api/v0/areas",
                "/api/v0/openapi.json",
                "/api/health",
            ]

            for endpoint in endpoints:
                response = await client.get(endpoint)

                # All endpoints should have at minimum these headers
                assert "X-Frame-Options" in response.headers, (
                    f"Missing X-Frame-Options on {endpoint}"
                )
                assert "X-Content-Type-Options" in response.headers, (
                    f"Missing X-Content-Type-Options on {endpoint}"
                )
                assert "Content-Security-Policy" in response.headers, (
                    f"Missing CSP on {endpoint}"
                )

    async def test_csp_form_action_restricted(self):
        """Test that CSP restricts form submission targets."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should restrict form actions to same origin
            assert "form-action 'self'" in csp

    async def test_csp_base_uri_restricted(self):
        """Test that CSP restricts base tag URLs."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should restrict base URI to same origin
            assert "base-uri 'self'" in csp


@pytest.mark.asyncio
class TestXSSProtection:
    """Specific tests for XSS input/output protection."""

    async def test_xss_output_protection_via_csp(self):
        """Test that CSP provides XSS output protection."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            # CSP should restrict script execution
            csp = response.headers["Content-Security-Policy"]
            assert "script-src" in csp
            assert "default-src 'self'" in csp

            # This prevents inline malicious scripts from executing
            # even if they somehow make it into responses

    async def test_mime_sniffing_protection(self):
        """Test MIME-sniffing protection prevents content type confusion attacks."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            # nosniff prevents browser from MIME-sniffing responses
            # This prevents XSS via content-type confusion
            assert response.headers["X-Content-Type-Options"] == "nosniff"

    async def test_frame_protection_prevents_clickjacking(self):
        """Test frame protection prevents clickjacking attacks."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            # Dual protection against framing
            assert response.headers["X-Frame-Options"] == "DENY"

            csp = response.headers["Content-Security-Policy"]
            assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
class TestOWASPSecurityHeaders:
    """Specific tests for OWASP security headers compliance."""

    async def test_all_owasp_recommended_headers_present(self):
        """Test that all OWASP recommended security headers are present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            # OWASP recommended headers
            required_headers = [
                "Content-Security-Policy",
                "X-Frame-Options",
                "X-Content-Type-Options",
                "Referrer-Policy",
                "Permissions-Policy",
                "Cross-Origin-Opener-Policy",
                "Cross-Origin-Resource-Policy",
                "Cross-Origin-Embedder-Policy",
            ]

            for header in required_headers:
                assert header in response.headers, (
                    f"Missing OWASP recommended header: {header}"
                )

    async def test_security_headers_values_are_secure(self):
        """Test that security header values are set to secure defaults."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v0/ping")

            # Verify secure values
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
            assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
