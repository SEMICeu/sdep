"""Tests for the API docs landing page."""

import pytest
from app.api.common_app import app_common
from app.api.domain_registry import API_DOMAINS, API_SCOPES, OAS_VERSION
from app.config import settings
from httpx import ASGITransport, AsyncClient


class TestDocsLandingPage:
    """Test suite for GET /docs landing page."""

    @pytest.mark.asyncio
    async def test_docs_landing_returns_html(self):
        """Test GET /docs returns 200 with HTML content."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_docs_landing_contains_version_links(self):
        """Test landing page contains links to versioned API docs."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        for domain in API_DOMAINS:
            assert domain.docs_path in body
            assert domain.openapi_path in body

    @pytest.mark.asyncio
    async def test_docs_landing_groups_domains_by_scope(self):
        """Each domain is listed under its own scope heading, EU-harmonized first."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        assert "<h2>API domains</h2>" in body
        assert body.index("<h3>EU-harmonized</h3>") < body.index(
            "<h3>Country-specific</h3>"
        )

        heading_at = {
            scope: body.index(f"<h3>{heading}</h3>") for scope, heading, _ in API_SCOPES
        }
        bounds = [*sorted(heading_at.values()), body.index("<h2>Common</h2>")]
        for domain in API_DOMAINS:
            start = heading_at[domain.scope]
            end = bounds[bounds.index(start) + 1]
            assert start < body.index(f'<a href="{domain.docs_path}">') < end, (
                domain.label
            )

    @pytest.mark.asyncio
    async def test_docs_landing_contains_api_status_tags(self):
        """Test landing page contains status tags for every API domain."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        for domain in API_DOMAINS:
            assert (
                f'<span class="status status-{domain.status}">{domain.status}</span>'
                in body
            )

    @pytest.mark.asyncio
    async def test_docs_landing_contains_version_diff_links(self):
        """Test landing page links the version diff for domains that have one."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        linked = [domain for domain in API_DOMAINS if domain.diff_url]
        assert linked, "expected at least one domain to publish a version diff"
        for domain in linked:
            assert f'<a href="{domain.diff_url}">Version diff</a>' in body

        for domain in API_DOMAINS:
            if domain.diff_url is None:
                assert domain.html.count("<a href=") == 2

    @pytest.mark.asyncio
    async def test_docs_landing_header_shows_version_and_oas_badges(self):
        """Test the deployment and OAS badges appear once, in the page header."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        version_badge = f'<span class="badge">{settings.api_version_label}</span>'
        oas_badge = f'<span class="badge badge-oas">OAS {OAS_VERSION}</span>'

        assert body.count(version_badge) == 1
        assert body.count(oas_badge) == 1
        assert f"{version_badge}{oas_badge}</h1>" in body

    @pytest.mark.asyncio
    async def test_docs_landing_contains_health_link(self):
        """Test landing page contains link to health endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        assert "/api/health" in response.text

    @pytest.mark.asyncio
    async def test_docs_landing_lists_ping_and_health_under_common(self):
        """Test the version-independent endpoints share one Common section, ping first."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        assert "<h2>Common</h2>" in body
        assert '<a href="/api/ping/docs">Ping</a>' in body
        assert '<a href="/api/health">Health</a>' in body
        assert body.index(">Ping</a>") < body.index(">Health</a>")

    @pytest.mark.asyncio
    async def test_docs_landing_contains_title(self):
        """Test landing page contains SDEP title."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        assert "SDEP" in response.text
        assert "Single Digital Entry Point" in response.text


class TestPingDocsPage:
    """The ping endpoint gets its own Swagger UI, with an Authorize option."""

    @pytest.mark.asyncio
    async def test_ping_docs_page_is_served(self):
        """Test GET /api/ping/docs returns the Swagger UI page."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/ping/docs")

        assert response.status_code == 200
        assert "swagger-ui" in response.text

    @pytest.mark.asyncio
    async def test_ping_docs_spec_covers_only_ping(self):
        """The page documents the ping endpoint, not the whole common app."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/ping/openapi.json")

        schema = response.json()

        assert response.status_code == 200
        assert list(schema["paths"]) == ["/ping"]

    @pytest.mark.asyncio
    async def test_ping_docs_spec_declares_the_mount_prefix(self):
        """Without a servers entry Swagger UI calls /ping instead of /api/ping."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            schema = (await client.get("/ping/openapi.json")).json()

        assert schema["servers"] == [{"url": "/api"}]

    @pytest.mark.asyncio
    async def test_ping_operation_declares_a_security_scheme(self):
        """Without a declared scheme Swagger UI shows no Authorize button."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            schema = (await client.get("/ping/openapi.json")).json()

        assert schema["paths"]["/ping"]["get"]["security"]
        assert schema["components"]["securitySchemes"]

    @pytest.mark.asyncio
    async def test_ping_endpoint_still_answers_on_its_own_path(self):
        """The docs page must not move or redirect the endpoint itself."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/ping", follow_redirects=False)

        assert response.status_code == 401
