"""Tests for audit log retention cleanup."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from app.main import app as _app  # noqa: F401  # pyright: ignore[reportUnusedImport]
from app.models.audit_log import AuditLog
from app.security.audit_retention import (
    BATCH_SIZE,
    audit_log_cleanup_loop,
    delete_old_audit_logs,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _make_audit_row(timestamp: datetime) -> AuditLog:
    """Create an AuditLog instance with the given timestamp."""
    return AuditLog(
        timestamp=timestamp,
        request_id="test-request-id",
        action="test",
        http_method="GET",
        path="/test",
        http_status_code=200,
        status_code="OK",
    )


def _mock_session_factory(engine: AsyncEngine):
    """Return a callable that mimics create_async_session() backed by the test engine."""
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return maker


@pytest.mark.asyncio
class TestDeleteOldAuditLogs:
    """Test delete_old_audit_logs function."""

    async def test_expired_rows_are_deleted(self, async_engine: AsyncEngine):
        """Rows older than the retention period are deleted."""
        factory = _mock_session_factory(async_engine)

        # Insert an old row
        async with factory() as session, session.begin():
            session.add(_make_audit_row(datetime.now(UTC) - timedelta(days=5)))

        with patch(
            "app.security.audit_retention.create_async_session",
            side_effect=factory,
        ):
            deleted = await delete_old_audit_logs(retention_days=1)

        assert deleted == 1

    async def test_recent_rows_are_preserved(self, async_engine: AsyncEngine):
        """Rows within the retention period are not deleted."""
        factory = _mock_session_factory(async_engine)

        # Insert a recent row
        async with factory() as session, session.begin():
            session.add(_make_audit_row(datetime.now(UTC) - timedelta(hours=1)))

        with patch(
            "app.security.audit_retention.create_async_session",
            side_effect=factory,
        ):
            deleted = await delete_old_audit_logs(retention_days=1)

        assert deleted == 0

    async def test_batching(self, async_engine: AsyncEngine):
        """Deletion works when there are more rows than BATCH_SIZE."""
        factory = _mock_session_factory(async_engine)
        count = BATCH_SIZE + 50
        old_ts = datetime.now(UTC) - timedelta(days=5)

        async with factory() as session, session.begin():
            for _ in range(count):
                session.add(_make_audit_row(old_ts))

        with patch(
            "app.security.audit_retention.create_async_session",
            side_effect=factory,
        ):
            deleted = await delete_old_audit_logs(retention_days=1)

        assert deleted == count


@pytest.mark.asyncio
class TestAuditLogCleanupLoop:
    """Test audit_log_cleanup_loop resilience."""

    async def test_exception_does_not_crash_loop(self):
        """An exception in one cycle does not stop the loop."""
        call_count = 0

        async def _mock_delete(retention_days: int) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient DB error")
            return 0

        with patch(
            "app.security.audit_retention.delete_old_audit_logs",
            side_effect=_mock_delete,
        ):
            task = asyncio.create_task(
                audit_log_cleanup_loop(retention_days=1, interval_seconds=0.01)
            )
            # Let a few cycles run (generous margin for e.g. slow CI runners)
            await asyncio.sleep(0.2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        # The loop continued past the first failure
        assert call_count >= 2
