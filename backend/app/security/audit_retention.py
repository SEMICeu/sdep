"""Automated audit log retention cleanup."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.db.config import create_async_session
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def delete_old_audit_logs(retention_days: int) -> int:
    """One-shot deletion of all audit log rows older than *retention_days*.

    Deletes in batches of BATCH_SIZE to avoid long-running transactions and
    excessive lock contention. Each batch runs in its own transaction.

    This is a pure coroutine that runs to completion and returns - it does not
    loop or sleep. It can be called standalone (e.g. in scripts, tests, or
    one-off maintenance) or by ``audit_log_cleanup_loop`` for recurring use.

    Returns the total number of rows deleted.
    """
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    total_deleted = 0

    while True:
        async with create_async_session() as session, session.begin():
            # Fetch a batch of expired row IDs first, then delete.
            # Two-step approach works on both PostgreSQL and SQLite
            # (SQLite does not support DELETE with a subquery containing LIMIT).
            rows = await session.execute(
                select(AuditLog.id).where(AuditLog.timestamp < cutoff).limit(BATCH_SIZE)
            )
            ids = rows.scalars().all()
            if not ids:
                break
            result = await session.execute(delete(AuditLog).where(AuditLog.id.in_(ids)))
            total_deleted += result.rowcount

        if len(ids) < BATCH_SIZE:
            break

    return total_deleted


async def audit_log_cleanup_loop(
    retention_days: int, interval_seconds: float = 3600.0
) -> None:
    """Infinite scheduling loop that periodically purges expired audit rows.

    On each cycle, calls ``delete_old_audit_logs`` to do the actual deletion,
    then sleeps for *interval_seconds* (default 3 600 s = 1 hour).

    Exceptions in a single cycle are caught and logged so the loop keeps
    running. The loop itself runs until the enclosing ``asyncio.Task`` is
    cancelled - which happens during FastAPI shutdown via the ``lifespan``
    context manager in ``main.py``.
    """
    # Wait before the first attempt so the database has time to become
    # available during application startup.
    await asyncio.sleep(interval_seconds)

    while True:
        try:
            deleted = await delete_old_audit_logs(retention_days)
            if deleted:
                logger.info("Audit log cleanup: deleted %d expired rows", deleted)
        except Exception:
            logger.exception("Audit log cleanup cycle failed")

        await asyncio.sleep(interval_seconds)
