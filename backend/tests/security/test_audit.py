"""Tests for audit log middleware."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from app.main import app
from app.security.audit import SKIP_PATHS, AuditLogMiddleware, _resolve_action
from fastapi import FastAPI, Response, status
from httpx import ASGITransport, AsyncClient


def _make_jwt(claims: dict) -> str:
    """Create an unsigned JWT for testing."""
    return jwt.encode(
        claims,
        key="test-secret-that-is-at-least-32-bytes",
        algorithm="HS256",
    )


def _make_audit_test_app(status_code: int) -> FastAPI:
    """Create a minimal app to exercise audit middleware status branches."""
    test_app = FastAPI()
    test_app.add_middleware(AuditLogMiddleware)

    @test_app.get("/api/ping")
    async def ping():
        return Response(status_code=status_code)

    return test_app


@pytest.mark.asyncio
class TestActionMapping:
    """Test action resolution from HTTP method + path."""

    @pytest.mark.parametrize(
        "method, path, expected_action, expected_type",
        [
            ("POST", "/api/ca/v1/areas", "create", "area"),
            ("GET", "/api/ca/v1/areas", "list", "area"),
            ("GET", "/api/ca/v1/areas/count", "count", "area"),
            ("GET", "/api/ca/v1/areas/abc-123", "read", "area"),
            ("DELETE", "/api/ca/v1/areas/abc-123", "delete", "area"),
            ("POST", "/api/str/v1/activities/bulk", "create_bulk", "activity"),
            ("GET", "/api/str/v1/areas", "list", "area"),
            ("GET", "/api/str/v1/areas/count", "count", "area"),
            ("GET", "/api/str/v1/areas/xyz-456", "read", "area"),
            ("GET", "/api/ca/v1/activities", "list", "activity"),
            ("GET", "/api/ca/v1/activities/count", "count", "activity"),
            ("POST", "/api/auth/v1/token", "token", "auth"),
            ("GET", "/api/ping", "ping", "system"),
        ],
    )
    async def test_action_mapping(self, method, path, expected_action, expected_type):
        """Test that all endpoint→action mappings produce correct results."""
        action, resource_type = _resolve_action(method, path)
        assert action == expected_action
        assert resource_type == expected_type

    async def test_unknown_path_fallback(self):
        """Test that unmatched paths fall back to 'unknown'."""
        action, resource_type = _resolve_action("GET", "/api/unknown/v1/test")
        assert action == "unknown"
        assert resource_type is None

    async def test_version_agnostic(self):
        """Test that action mapping works for any API version."""
        action, resource_type = _resolve_action("POST", "/api/ca/v1/areas")
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
                response = await client.get("/api/ping")
                # Allow background task to execute
                await asyncio.sleep(0.1)

                mock_write.assert_called_once()
                record = mock_write.call_args[0][0]
                assert record.action == "ping"
                assert record.http_method == "GET"
                assert record.path == "/api/ping"
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
                await client.get("/api/ca/v1/openapi.json")
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
                await client.get("/api/ca/v1/areas")
                await asyncio.sleep(0.1)

                record = mock_write.call_args[0][0]
                assert record.http_status_code >= 400
                assert record.status_code == "NOK"

    async def test_success_status_logs_jwt_roles(self):
        """Test that successful requests log roles extracted from the bearer token."""
        token = _make_jwt({"realm_access": {"roles": ["role-a", "role-b"]}})
        transport = ASGITransport(app=_make_audit_test_app(status.HTTP_200_OK))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                await client.get(
                    "/api/ping", headers={"Authorization": f"Bearer {token}"}
                )
                await asyncio.sleep(0.1)

                record = mock_write.call_args[0][0]
                assert record.http_status_code < 400
                assert record.roles == "role-a,role-b"

    async def test_forbidden_status_logs_unauthorized_roles(self):
        """Test that forbidden requests are logged as unauthorized."""
        transport = ASGITransport(app=_make_audit_test_app(status.HTTP_403_FORBIDDEN))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record", new_callable=AsyncMock
            ) as mock_write:
                await client.get(
                    "/api/ping", headers={"Authorization": "Bearer invalid"}
                )
                await asyncio.sleep(0.1)

                record = mock_write.call_args[0][0]
                assert record.http_status_code == 403
                assert record.roles == "UNAUTHORIZED"

    async def test_audit_write_failure_does_not_break_request(self):
        """Test that audit write failure doesn't break the request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.security.audit._write_audit_record",
                side_effect=Exception("DB connection failed"),
            ):
                # Request should still succeed despite audit failure
                response = await client.get("/api/ping")
                assert response.status_code in (200, 401)

    async def test_audit_record_logged_to_stdout(self):
        """Test that audit record is emitted as structured JSON to stdout."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch("app.security.audit._write_audit_record", new_callable=AsyncMock),
                patch("app.security.audit.audit_logger") as mock_logger,
            ):
                await client.get("/api/ping")
                await asyncio.sleep(0.1)

                mock_logger.info.assert_called_once()
                raw = mock_logger.info.call_args[0][0]
                record = json.loads(raw)
                assert record["action"] == "ping"
                assert record["httpMethod"] == "GET"
                assert record["path"] == "/api/ping"
                assert "timestamp" in record
                assert "requestId" in record
                assert "httpStatusCode" in record
                assert "statusCode" in record
                assert "durationMs" in record

    async def test_skip_paths_are_complete(self):
        """Test that skip paths match the documented set."""
        expected = {
            "/",
            "/favicon.ico",
            "/api/docs",
            "/api/health",
            "/api/auth/v1/openapi.json",
            "/api/auth/v1/docs",
            "/api/ca/v1/openapi.json",
            "/api/ca/v1/docs",
            "/api/str/v1/openapi.json",
            "/api/str/v1/docs",
        }
        assert expected == SKIP_PATHS
