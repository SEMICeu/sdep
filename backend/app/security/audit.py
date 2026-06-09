"""Audit log middleware for tracking API requests."""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

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
        "/api/ca/v2/openapi.json",
        "/api/ca/v2/docs",
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
    """Read roles from the JWT payload stashed on ``request.state`` by the auth dependency.

    The dependency has already verified the signature; the audit middleware does
    not re-decode the token (would double signature verification per request).
    Returns None when no payload was stashed (e.g. unauthenticated endpoints).
    """
    payload = getattr(request.state, "jwt_payload", None)
    if not payload:
        return None
    roles_list = payload.get("realm_access", {}).get("roles", [])
    return ",".join(roles_list) if roles_list else None


_pending_audit_writes: set[asyncio.Task] = set()


async def _write_audit_record(record: AuditLog) -> None:
    """Write audit record to database in background. Failures are logged, never raised."""
    try:
        async with create_async_session() as session, session.begin():
            session.add(record)
    except Exception:
        logger.warning("Failed to write audit log record", exc_info=True)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware that logs API requests to the audit_log table.

    - Skips low-value paths (health, docs, root)
    - Extracts JWT roles only after signature verification
    - Writes audit records asynchronously to avoid blocking responses
    - Audit failures never break the request
    """

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

        # Extract audit data. The auth dependency stashes the verified JWT
        # payload on request.state for any request that reached a protected
        # handler — including 403s raised by RequireRoles. 401s never get
        # that far, so roles stays None there. The HTTP status column already
        # encodes "rejected" (401) vs "insufficient permission" (403).
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

        # Write asynchronously - never block the response.
        # Keep a strong reference in _pending_audit_writes until the task
        # completes, otherwise the task can be garbage-collected mid-flight.
        task = asyncio.create_task(_write_audit_record(record))
        _pending_audit_writes.add(task)
        task.add_done_callback(_pending_audit_writes.discard)

        return response
