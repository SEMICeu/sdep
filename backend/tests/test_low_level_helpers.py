from __future__ import annotations

import importlib
import importlib.util
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from app.crud import activity as activity_crud
from app.db import config as db_config


@pytest.mark.asyncio
async def test_activity_crud_empty_bulk_helpers_return_early():
    session = AsyncMock()

    await activity_crud.bulk_mark_as_ended(session, [], 1)
    await activity_crud.bulk_create(session, [])
    current = await activity_crud.get_current_by_activity_ids(session, [], 1)
    deactivated = await activity_crud.get_deactivated_activity_ids(session, [])

    session.execute.assert_not_called()
    session.flush.assert_not_called()
    assert current == {}
    assert deactivated == set()


@pytest.mark.asyncio
async def test_get_async_db_read_only_yields_session_from_factory(monkeypatch):
    expected_session = object()

    class _Context(AbstractAsyncContextManager):
        async def __aenter__(self):
            return expected_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(db_config, "AsyncSessionReadOnly", lambda: _Context())

    generator = db_config.get_async_db_read_only()
    yielded = await anext(generator)

    assert yielded is expected_session

    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_get_async_db_yields_session_from_transaction_factory(monkeypatch):
    expected_session = object()

    class _Context(AbstractAsyncContextManager):
        async def __aenter__(self):
            return expected_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _SessionFactory:
        def begin(self):
            return _Context()

    monkeypatch.setattr(db_config, "AsyncSessionLocal", _SessionFactory())

    generator = db_config.get_async_db()
    yielded = await anext(generator)

    assert yielded is expected_session

    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_write_audit_record_logs_failures(monkeypatch):
    audit_path = Path(__file__).resolve().parents[1] / "app" / "security" / "audit.py"
    spec = importlib.util.spec_from_file_location("audit_test_module", audit_path)
    assert spec is not None and spec.loader is not None
    audit_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit_module)
    warnings: list[str] = []

    class _BrokenContext(AbstractAsyncContextManager):
        async def __aenter__(self):
            raise RuntimeError("db unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(audit_module, "create_async_session", lambda: _BrokenContext())
    monkeypatch.setattr(
        audit_module.logger,
        "warning",
        lambda message, exc_info=True: warnings.append(message),
    )

    await audit_module._write_audit_record(object())

    assert warnings == ["Failed to write audit log record"]
