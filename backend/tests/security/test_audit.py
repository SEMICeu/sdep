"""Tests for audit log middleware."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from app.main import app
from app.security.audit import SKIP_PATHS, _resolve_action
from httpx import ASGITransport, AsyncClient
from jose import jwt


def _make_jwt(claims: dict) -> str:
    """Create an unsigned JWT for testing."""
    return jwt.encode(claims, key="test-secret", algorithm="HS256")


@pytest.mark.asyncio
class TestActionMapping:
    """Test action resolution from HTTP method + path."""

    @pytest.mark.parametrize(
        "method, path, expected_action, expected_type",
        [
            ("POST", "/api/v0/ca/areas", "create", "area"),
            ("GET", "/api/v0/ca/areas", "list", "area"),
            ("GET", "/api/v0/ca/areas/count", "count", "area"),
            ("GET", "/api/v0/ca/areas/abc-123", "read", "area"),
            ("DELETE", "/api/v0/ca/areas/abc-123", "delete", "area"),
            ("POST", "/api/v0/str/activities/bulk", "create_bulk", "activity"),
            ("GET", "/api/v0/str/areas", "list", "area"),
            ("GET", "/api/v0/str/areas/count", "count", "area"),
            ("GET", "/api/v0/str/areas/xyz-456", "read", "area"),
            ("GET", "/api/v0/ca/activities", "list", "activity"),
            ("GET", "/api/v0/ca/activities/count", "count", "activity"),
            ("POST", "/api/v0/auth/token", "token", "auth"),
            ("GET", "/api/v0/ping", "ping", "system"),
        ],
    )
    async def test_action_mapping(self, method, path, expected_action, expected_type):
        """Test that all endpoint→action mappings produce correct results."""
        action, resource_type = _resolve_action(method, path)
        assert action == expected_action
        assert resource_type == expected_type

    async def test_unknown_path_fallback(self):
        """Test that unmatched paths fall back to 'unknown'."""
        action, resource_type = _resolve_action("GET", "/api/v0/unknown")
        assert action == "unknown"
        assert resource_type is None

    async def test_version_agnostic(self):
        """Test that action mapping works for any API version."""
        action, resource_type = _resolve_action("POST", "/api/v1/ca/areas")
        assert action == "create"
        assert resource_type == "area"


@pytest.mark.asyncio
class TestAuditMiddleware:
    """Test audit log middleware integration."""

    async def test_audit_record_created_for_business_endpoint(self):
        """Test that audit record is created for business endpoints."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                response = await client.get("/api/v0/ping")
                # Allow background task to execute
                await asyncio.sleep(0.1)

                mock_write.assert_called_once()
                record = mock_write.call_args[0][0]
                assert record.action == "ping"
                assert record.http_method == "GET"
                assert record.path == "/api/v0/ping"
                assert record.http_status_code == response.status_code
                assert record.request_id is not None
                assert record.duration_ms is not None

    async def test_audit_skipped_for_health_endpoint(self):
        """Test that audit is skipped for health/docs endpoints."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                await client.get("/api/health")
                await asyncio.sleep(0.1)
                mock_write.assert_not_called()

    async def test_audit_skipped_for_root(self):
        """Test that audit is skipped for root endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                await client.get("/")
                await asyncio.sleep(0.1)
                mock_write.assert_not_called()

    async def test_audit_skipped_for_openapi(self):
        """Test that audit is skipped for OpenAPI docs endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                await client.get("/api/v0/openapi.json")
                await asyncio.sleep(0.1)
                mock_write.assert_not_called()

    async def test_failure_status_logged_with_nok(self):
        """Test that failure status codes are logged with status_code='NOK'."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                # Hit a protected endpoint without auth → expect 401
                await client.get("/api/v0/ca/areas")
                await asyncio.sleep(0.1)

                record = mock_write.call_args[0][0]
                assert record.http_status_code >= 400
                assert record.status_code == "NOK"

    async def test_audit_write_failure_does_not_break_request(self):
        """Test that audit write failure doesn't break the request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record",
                side_effect=Exception("DB connection failed"),
            ):
                # Request should still succeed despite audit failure
                response = await client.get("/api/v0/ping")
                assert response.status_code in (200, 401)

    async def test_audit_record_logged_to_stdout(self):
        """Test that audit record is emitted as structured JSON to stdout."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch("app.security.audit._write_audit_record", new_callable=AsyncMock),
                patch("app.security.audit.audit_logger") as mock_logger,
            ):
                await client.get("/api/v0/ping")
                await asyncio.sleep(0.1)

                mock_logger.info.assert_called_once()
                raw = mock_logger.info.call_args[0][0]
                record = json.loads(raw)
                assert record["action"] == "ping"
                assert record["httpMethod"] == "GET"
                assert record["path"] == "/api/v0/ping"
                assert "timestamp" in record
                assert "requestId" in record
                assert "httpStatusCode" in record
                assert "statusCode" in record
                assert "durationMs" in record

    async def test_skip_paths_are_complete(self):
        """Test that skip paths match the documented set."""
        expected = {
            "/",
            "/api/docs",
            "/api/health",
            "/api/v0/openapi.json",
            "/api/v0/docs",
        }
        assert expected == SKIP_PATHS
