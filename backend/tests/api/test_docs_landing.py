"""Tests for the API docs landing page."""

import pytest
from app.api.common_app import app_common
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
        assert "/api/auth/v1/docs" in body
        assert "/api/ca/v1/docs" in body
        assert "/api/ca/v2/docs" in body
        assert "/api/str/v1/docs" in body
        assert "/api/auth/v1/openapi.json" in body
        assert "/api/ca/v1/openapi.json" in body
        assert "/api/ca/v2/openapi.json" in body
        assert "/api/str/v1/openapi.json" in body

    @pytest.mark.asyncio
    async def test_docs_landing_contains_health_link(self):
        """Test landing page contains link to health endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        assert "/api/health" in response.text

    @pytest.mark.asyncio
    async def test_docs_landing_contains_title(self):
        """Test landing page contains SDEP title."""
        async with AsyncClient(
            transport=ASGITransport(app=app_common), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        assert "SDEP" in response.text
        assert "Single Digital Entry Point" in response.text
