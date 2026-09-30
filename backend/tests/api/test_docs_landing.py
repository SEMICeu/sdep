"""Tests for the API docs landing page."""

from html import escape

import pytest
from app.api.common_app import app_common
from app.api.domain_registry import (
    API_DOMAINS,
    API_GROUPS,
    API_SCOPES,
    OAS_VERSION,
)
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

    @staticmethod
    def _sections(body: str) -> dict[str, str]:
        """The HTML of each API_GROUPS section, from its heading up to the next one."""
        starts = [
            body.index(f"<h2>{escape(heading)}</h2>") for _, heading in API_GROUPS
        ]
        assert starts == sorted(starts)
        ends = [*starts[1:], body.index("<h2>Common</h2>")]
        return {
            group: body[start:end]
            for (group, _), start, end in zip(API_GROUPS, starts, ends, strict=True)
        }

    @pytest.mark.asyncio
    async def test_docs_landing_groups_domains_by_group_then_scope(self):
        """Each domain is listed in its group section, under its scope heading."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        sections = self._sections(response.text)
        for domain in API_DOMAINS:
            section = sections[domain.group]
            # Scope headings in API_SCOPES order; the domain sits under its own
            scope_at = [
                (section.index(f"<h3>{heading}</h3>"), scope)
                for scope, heading, _ in API_SCOPES
                if f"<h3>{heading}</h3>" in section
            ]
            assert scope_at == sorted(scope_at)
            row_at = section.index(f'<a href="{domain.docs_path}">')
            assert max(s for s in scope_at if s[0] < row_at)[1] == domain.scope, (
                domain.label
            )

    @pytest.mark.asyncio
    async def test_docs_landing_leaves_out_a_scope_without_domains(self):
        """Auth is the only domain in its section, so only its scope heading shows."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        section = self._sections(response.text)["authentication"]
        assert "<h3>EU-harmonized</h3>" in section
        assert "<h3>Country-specific</h3>" not in section

    @pytest.mark.asyncio
    async def test_docs_landing_sorts_domains_alphabetically_within_group(self):
        """Within a group and scope the domains are listed by label, whatever the registry order."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        for group, _ in API_GROUPS:
            for scope, _, _ in API_SCOPES:
                labels = [
                    d.label
                    for d in API_DOMAINS
                    if d.group == group and d.scope == scope
                ]
                listed = sorted(labels, key=lambda label: body.index(f">{label}</a>"))
                assert listed == sorted(labels), (group, scope)

    @pytest.mark.asyncio
    async def test_docs_landing_shows_the_spelled_out_acronym_per_domain(self):
        """Each row ends with the domain name, right-aligned, so the acronym needs no lookup."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        for domain in API_DOMAINS:
            row = domain.html
            assert row in body, domain.label
            assert row.endswith(f'<span class="name">{domain.name}</span>\n    </div>')

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
        """Test the version, environment and OAS badges appear once, in the page header."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        body = response.text
        version_badge = f'<span class="badge">{settings.api_version}</span>'
        environment_badge = f'<span class="badge">{settings.DTAP}</span>'
        oas_badge = f'<span class="badge badge-oas">OAS {OAS_VERSION}</span>'

        assert body.count(version_badge) == 1
        assert body.count(environment_badge) == 1
        assert body.count(oas_badge) == 1
        assert f"{version_badge}{environment_badge}{oas_badge}</h1>" in body

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
        assert '<span class="name">Application + database</span>' in body
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
