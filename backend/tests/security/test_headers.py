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
            # Use /api/ping - expect 401 but headers should be present
            response = await client.get("/api/ping")

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
            assert response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"

            # Permissions policy
            assert "Permissions-Policy" in response.headers
            permissions = response.headers["Permissions-Policy"]
            assert "geolocation=()" in permissions
            assert "microphone=()" in permissions
            assert "camera=()" in permissions

    async def test_csp_allows_swagger_ui_cdn_on_docs(self):
        """Test that CSP on Swagger docs paths allows CDN resources."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/auth/v1/docs")

            csp = response.headers["Content-Security-Policy"]

            assert "https://cdn.jsdelivr.net" in csp
            assert "script-src" in csp and "cdn.jsdelivr.net" in csp
            assert "style-src" in csp and "cdn.jsdelivr.net" in csp
            assert "font-src" in csp and "cdn.jsdelivr.net" in csp

    async def test_csp_blocks_unsafe_eval(self):
        """Test that CSP does not allow unsafe-eval (XSS protection)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should NOT contain unsafe-eval (blocks eval-based XSS)
            assert "'unsafe-eval'" not in csp

    async def test_csp_restricts_object_sources(self):
        """Test that CSP blocks object/embed tags (XSS protection)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should block object/embed
            assert "object-src 'none'" in csp

    async def test_csp_prevents_framing(self):
        """Test that CSP prevents framing (clickjacking protection)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should prevent framing
            assert "frame-ancestors 'none'" in csp

    async def test_sensitive_endpoint_auth(self):
        """Test that sensitive auth endpoints get cache control headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Auth endpoint is sensitive - should have no-cache
            response = await client.post(
                "/api/auth/v1/token",
                data={"username": "test", "password": "test"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Check cache control for sensitive endpoint
            cache_control = response.headers.get("Cache-Control", "")
            assert "no-store" in cache_control or "no-cache" in cache_control

    async def test_sensitive_endpoint_openapi(self):
        """Test that OpenAPI schema endpoint gets cache control headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ca/v1/openapi.json")

            # OpenAPI is marked as sensitive
            cache_control = response.headers.get("Cache-Control", "")
            assert "no-store" in cache_control or "no-cache" in cache_control
            assert response.headers.get("Pragma") == "no-cache"

    async def test_hsts_enabled(self):
        """Test that HSTS is enabled as defense-in-depth."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

            hsts = response.headers.get("Strict-Transport-Security")
            assert hsts is not None
            assert "max-age=" in hsts
            assert "includeSubDomains" in hsts

    async def test_all_api_endpoints_have_headers(self):
        """Test that all API endpoints receive security headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            endpoints = [
                "/api/ping",
                "/api/ca/v1/areas",
                "/api/ca/v1/openapi.json",
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
            response = await client.get("/api/ping")

            csp = response.headers["Content-Security-Policy"]

            # Should restrict form actions to same origin
            assert "form-action 'self'" in csp

    async def test_csp_base_uri_restricted(self):
        """Test that CSP restricts base tag URLs."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

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
            response = await client.get("/api/ping")

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
            response = await client.get("/api/ping")

            # nosniff prevents browser from MIME-sniffing responses
            # This prevents XSS via content-type confusion
            assert response.headers["X-Content-Type-Options"] == "nosniff"

    async def test_frame_protection_prevents_clickjacking(self):
        """Test frame protection prevents clickjacking attacks."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

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
            response = await client.get("/api/ping")

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
            response = await client.get("/api/ping")

            # Verify secure values
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
            assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"


@pytest.mark.asyncio
class TestRouteSpecificCSP:
    """Tests for route-specific Content-Security-Policy."""

    async def test_csp_strict_on_root(self):
        """Root URL has strict CSP — no 'unsafe-inline', no CDN."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

            csp = response.headers["Content-Security-Policy"]
            assert "'unsafe-inline'" not in csp
            assert "cdn.jsdelivr.net" not in csp

    async def test_csp_strict_on_api_endpoints(self):
        """API endpoints have strict CSP — no 'unsafe-inline', no CDN."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ping")

            csp = response.headers["Content-Security-Policy"]
            assert "'unsafe-inline'" not in csp
            assert "cdn.jsdelivr.net" not in csp

    async def test_csp_landing_allows_inline_style_only(self):
        """Docs landing page allows 'unsafe-inline' in style-src only."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/docs")

            csp = response.headers["Content-Security-Policy"]

            # style-src should allow unsafe-inline (for the inline <style>)
            for directive in csp.split(";"):
                if "style-src" in directive:
                    assert "'unsafe-inline'" in directive
                elif "script-src" in directive:
                    assert "'unsafe-inline'" not in directive

            # No CDN needed on landing page
            assert "cdn.jsdelivr.net" not in csp

    async def test_csp_relaxed_on_swagger_docs(self):
        """Swagger UI docs pages have relaxed CSP with CDN and 'unsafe-inline'."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for path in [
                "/api/auth/v1/docs",
                "/api/ca/v1/docs",
                "/api/ca/v2/docs",
                "/api/str/v1/docs",
            ]:
                response = await client.get(path)

                csp = response.headers["Content-Security-Policy"]
                assert "'unsafe-inline'" in csp, f"Missing 'unsafe-inline' on {path}"
                assert "cdn.jsdelivr.net" in csp, f"Missing CDN on {path}"

    async def test_csp_common_directives_on_all_paths(self):
        """All paths share the same base security directives."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            paths = ["/", "/api/ping", "/api/docs", "/api/auth/v1/docs"]

            for path in paths:
                response = await client.get(path)
                csp = response.headers["Content-Security-Policy"]

                assert "default-src 'self'" in csp, f"Missing default-src on {path}"
                assert "frame-ancestors 'none'" in csp, (
                    f"Missing frame-ancestors on {path}"
                )
                assert "object-src 'none'" in csp, f"Missing object-src on {path}"
                assert "base-uri 'self'" in csp, f"Missing base-uri on {path}"
                assert "form-action 'self'" in csp, f"Missing form-action on {path}"
