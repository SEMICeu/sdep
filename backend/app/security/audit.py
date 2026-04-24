"""Audit log middleware for tracking API requests."""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime

from fastapi import Request, Response
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.db.config import create_async_session
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")

# Paths to skip auditing (high-frequency, low-value)
SKIP_PATHS = frozenset(
    {
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
)

# Action mapping: (method, regex_pattern) -> (action, resource_type)
# Order matters: more specific patterns first
_ACTION_RULES: list[tuple[str, re.Pattern, str, str]] = [
    ("GET", re.compile(r"^/api/ca/v\d+/areas/count$"), "count", "area"),
    ("GET", re.compile(r"^/api/ca/v\d+/areas/([^/]+)$"), "read", "area"),
    ("POST", re.compile(r"^/api/ca/v\d+/areas$"), "create", "area"),
    ("GET", re.compile(r"^/api/ca/v\d+/areas$"), "list", "area"),
    ("DELETE", re.compile(r"^/api/ca/v\d+/areas/([^/]+)$"), "delete", "area"),
    ("GET", re.compile(r"^/api/str/v\d+/areas/count$"), "count", "area"),
    ("GET", re.compile(r"^/api/str/v\d+/areas/([^/]+)$"), "read", "area"),
    ("GET", re.compile(r"^/api/str/v\d+/areas$"), "list", "area"),
    ("POST", re.compile(r"^/api/str/v\d+/activities/bulk$"), "create_bulk", "activity"),
    ("GET", re.compile(r"^/api/ca/v\d+/activities/count$"), "count", "activity"),
    ("GET", re.compile(r"^/api/ca/v\d+/activities$"), "list", "activity"),
    ("POST", re.compile(r"^/api/auth/v\d+/token$"), "token", "auth"),
    ("GET", re.compile(r"^/api/ping$"), "ping", "system"),
]


def _resolve_action(method: str, path: str) -> tuple[str, str | None]:
    """Derive action and resource_type from HTTP method and path.

    Returns:
        Tuple of (action, resource_type).
    """
    for rule_method, pattern, action, resource_type in _ACTION_RULES:
        if method == rule_method:
            match = pattern.match(path)
            if match:
                return action, resource_type
    return "unknown", None


def _extract_jwt_roles(request: Request) -> str | None:
    """Extract roles from JWT token without verification.

    The actual authentication/verification happens in route dependencies.
    This is read-only extraction for audit purposes.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    try:
        payload = jwt.decode(
            token,
            key="",  # No key needed when not verifying
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
        # Extract roles from Keycloak realm_access claim
        roles_list = payload.get("realm_access", {}).get("roles", [])
        return ",".join(roles_list) if roles_list else None
    except Exception:
        logger.debug("Failed to decode JWT for audit logging", exc_info=True)
        return None


async def _write_audit_record(record: AuditLog) -> None:
    """Write audit record to database in background. Failures are logged, never raised."""
    try:
        async with create_async_session() as session, session.begin():
            session.add(record)
    except Exception as exc:
        logger.warning("Failed to write audit log record: %s", exc)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware that logs API requests to the audit_log table.

    - Skips low-value paths (health, docs, root)
    - Extracts JWT roles without verification (auth happens in route deps)
    - Writes audit records asynchronously to avoid blocking responses
    - Audit failures never break the request
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Intercept request/response and create audit record."""
        path = request.url.path

        # Skip low-value endpoints
        if path in SKIP_PATHS:
            return await call_next(request)

        # Record timing
        request_id = str(uuid.uuid4())
        start = time.monotonic()

        # Process request
        response = await call_next(request)

        duration_ms = int((time.monotonic() - start) * 1000)

        # Extract audit data
        method = request.method
        roles = _extract_jwt_roles(request)
        action, resource_type = _resolve_action(method, path)

        # Build audit record
        record = AuditLog(
            request_id=request_id,
            roles=roles,
            resource_type=resource_type,
            action=action,
            http_method=method,
            path=path[:512],
            http_status_code=response.status_code,
            status_code="OK" if response.status_code < 400 else "NOK",
            duration_ms=duration_ms,
        )

        # Emit structured JSON to stdout for real-time observability
        audit_logger.info(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "requestId": request_id,
                    "roles": roles,
                    "resourceType": resource_type,
                    "action": action,
                    "httpMethod": method,
                    "path": path[:512],
                    "httpStatusCode": response.status_code,
                    "statusCode": "OK" if response.status_code < 400 else "NOK",
                    "durationMs": duration_ms,
                }
            )
        )

        # Write asynchronously - never block the response
        # Store reference to prevent task from being garbage-collected
        task = asyncio.create_task(_write_audit_record(record))
        task.add_done_callback(
            lambda t: t.result() if not t.cancelled() and not t.exception() else None
        )

        return response
