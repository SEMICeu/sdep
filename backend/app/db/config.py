"""Async database configuration and session management."""

from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create database URL using SQLAlchemy URL builder for better security
# Using postgres as dialect, and asyncpg as driver
database_url = URL.create(
    "postgresql+asyncpg",
    database=settings.POSTGRES_DB_NAME,
    host=settings.POSTGRES_HOST,
    password=settings.POSTGRES_DB_PASSWORD,
    port=settings.POSTGRES_PORT,
    username=settings.POSTGRES_DB_USER,
)

# Additional connection args for asyncpg
connect_args = {
    "server_settings": {"application_name": settings.APP_NAME},
    "command_timeout": 60,
}

# Create async engine
async_engine: AsyncEngine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_size=5,
    max_overflow=10,
    connect_args=connect_args,
)

# Create async session factories
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,  # Enable autoflush for better consistency
    autocommit=False,
)

# Read-only session factory with optimizations
AsyncSessionReadOnly = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # No flushing for read-only
    autocommit=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    """
    Modern async dependency for write operations with automatic transaction management.

    Uses context managers for:
    - Automatic session cleanup
    - Automatic transaction handling (commit/rollback)
    - Proper resource management
    """
    async with AsyncSessionLocal.begin() as session:
        yield session
        # Automatic commit on success, rollback on exception


async def get_async_db_read_only() -> AsyncGenerator[AsyncSession]:
    """
    Optimized async dependency for read-only database operations.

    Benefits:
    - No transaction overhead for read operations
    - Better performance for queries
    - Automatic session cleanup
    """
    async with AsyncSessionReadOnly() as session:
        yield session
        # Automatic session cleanup


# Helper for using async sessions outside of FastAPI dependencies
def create_async_session() -> AbstractAsyncContextManager[AsyncSession]:
    """Create an async session for use outside of FastAPI dependencies."""
    return AsyncSessionLocal()

