from __future__ import annotations

import asyncio
import json

import pytest
from app.api.common.routers import health as health_router
from app.api.common.routers import ping as ping_router
from app.api.domains.auth.v1 import get_openapi_json
from app.api.domains.ca.v1 import get_openapi_json as get_ca_openapi_json
from app.api.domains.rep.v1 import get_openapi_json as get_rep_openapi_json
from app.api.domains.str.v1 import get_openapi_json as get_str_openapi_json
from app.main import lifespan, root
from app.security.audit_retention import audit_log_cleanup_loop
from app.security.headers import ApiSecurityHeadersMiddleware, SecurityHeadersMiddleware
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_root_and_openapi_json_endpoint():
    assert await root() == "OK"

    response = await get_openapi_json()

    assert response.media_type == "application/json"
    body = bytes(response.body)
    parsed = json.loads(body)
    assert "openapi" in parsed
    assert body.startswith(b"{\n")

    ca_response = await get_ca_openapi_json()
    str_response = await get_str_openapi_json()
    rep_response = await get_rep_openapi_json()
    assert ca_response.media_type == "application/json"
    assert str_response.media_type == "application/json"
    assert rep_response.media_type == "application/json"


@pytest.mark.asyncio
async def test_lifespan_cancels_cleanup_task_and_disposes_engine(monkeypatch):
    task_cancelled = {"value": False}
    disposed = {"value": False}

    async def fake_cleanup_loop(retention_days: int):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            task_cancelled["value"] = True
            raise

    async def fake_dispose(self):
        disposed["value"] = True

    monkeypatch.setattr("app.main.audit_log_cleanup_loop", fake_cleanup_loop)
    monkeypatch.setattr(
        "app.main.async_engine", type("Engine", (), {"dispose": fake_dispose})()
    )

    async with lifespan(FastAPI()):
        await asyncio.sleep(0)

    assert task_cancelled["value"] is True
    assert disposed["value"] is True


@pytest.mark.asyncio
async def test_health_database_check_and_endpoint_statuses(monkeypatch):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, query):
            return 1

    monkeypatch.setattr(health_router, "create_async_session", lambda: _Session())
    assert await health_router.check_database_available() == "OK"

    response = Response()
    assert await health_router.health(response) == {"database_available": "OK"}
    assert response.status_code == 200

    class _BrokenSession(_Session):
        async def execute(self, query):
            raise RuntimeError("db down")

    monkeypatch.setattr(health_router, "create_async_session", lambda: _BrokenSession())
    assert await health_router.check_database_available() == "NOK"

    response = Response()
    assert await health_router.health(response) == {"database_available": "NOK"}
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ping_endpoint_returns_ok_status():
    result = await ping_router.ping({"sub": "ok"})
    assert result.status == "OK"


@pytest.mark.asyncio
async def test_security_header_middlewares_cover_remaining_branches():
    inner = FastAPI()

    @inner.get("/public")
    async def public():
        return {"ok": True}

    hsts_app = FastAPI()
    hsts_app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=True,
        hsts_max_age=123,
        enable_csp=False,
    )

    @hsts_app.get("/public")
    async def public_hsts():
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=hsts_app), base_url="http://test"
    ) as client:
        response = await client.get("/public")
    assert (
        response.headers["Strict-Transport-Security"]
        == "max-age=123; includeSubDomains; preload"
    )

    api_app = FastAPI()
    api_app.add_middleware(ApiSecurityHeadersMiddleware)

    @api_app.get("/api/value")
    async def api_value():
        return {"ok": True}

    @api_app.get("/public")
    async def public_value():
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        api_response = await client.get("/api/value")
        public_response = await client.get("/public")

    assert (
        api_response.headers["Cache-Control"]
        == "no-store, no-cache, must-revalidate, private"
    )
    assert api_response.headers["X-Frame-Options"] == "DENY"
    assert "Cache-Control" not in public_response.headers


@pytest.mark.asyncio
async def test_audit_log_cleanup_loop_logs_success_and_continues_on_error(monkeypatch):
    sleep_calls = {"count": 0}
    delete_calls = {"count": 0}
    infos: list[str] = []
    exceptions: list[str] = []

    async def fake_sleep(seconds: float):
        sleep_calls["count"] += 1
        if sleep_calls["count"] >= 3:
            raise asyncio.CancelledError

    async def fake_delete(retention_days: int):
        delete_calls["count"] += 1
        if delete_calls["count"] == 1:
            return 2
        raise RuntimeError("cycle failed")

    monkeypatch.setattr("app.security.audit_retention.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "app.security.audit_retention.delete_old_audit_logs", fake_delete
    )
    monkeypatch.setattr(
        "app.security.audit_retention.logger.info",
        lambda message, deleted: infos.append(message % deleted),
    )
    monkeypatch.setattr(
        "app.security.audit_retention.logger.exception",
        lambda message: exceptions.append(message),
    )

    with pytest.raises(asyncio.CancelledError):
        await audit_log_cleanup_loop(retention_days=7, interval_seconds=0)

    assert any("deleted 2 expired rows" in message for message in infos)
    assert exceptions == ["Audit log cleanup cycle failed"]
