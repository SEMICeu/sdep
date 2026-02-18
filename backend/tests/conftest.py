"""Test configuration and fixtures."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from app.db.config import Base
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine() -> AsyncGenerator[AsyncEngine]:
    """
    Create a test database engine with separate test database.

    Strategy:
    - Local/Unit testing: uses SQLite in-memory database (no postgres required)
    - CI/Docker: uses DATABASE_URL environment variable if set (postgres)
    - Tables created for each test function for complete isolation
    - Supports pytest-xdist parallel testing with worker-specific databases
    """
    # Check if DATABASE_URL is set by CI/Docker (use postgres)
    database_url_env = os.environ.get("DATABASE_URL")

    if database_url_env:
        # CI/Docker mode: use PostgreSQL
        # Support pytest-xdist parallel testing by adding worker_id to database name
        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "")
        if worker_id:
            # Modify the database URL to include worker_id
            from sqlalchemy.engine.url import make_url

            url_obj = make_url(database_url_env)
            base_db_name = url_obj.database
            url_obj = url_obj.set(database=f"{base_db_name}_{worker_id}")
            test_db_url = str(url_obj)
            test_db_name = url_obj.database
            print(f"TEST DB: Using DATABASE_URL with worker_id: {test_db_url}")
        else:
            test_db_url = database_url_env
            from sqlalchemy.engine.url import make_url

            url_obj = make_url(database_url_env)
            test_db_name = url_obj.database
            print(f"TEST DB: Using DATABASE_URL: {database_url_env}")

        # Connect to postgres database to create test database
        from sqlalchemy import text
        from sqlalchemy.engine.url import make_url

        url_obj = make_url(test_db_url)
        admin_db_url = url_obj.set(database="postgres")

        admin_engine = create_async_engine(admin_db_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin_engine.connect() as conn:
                # Check if test database exists
                result = await conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": test_db_name},
                )
                if not result.fetchone():
                    # Create test database
                    print(f"TEST DB: Creating database '{test_db_name}'")
                    await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
                else:
                    print(f"TEST DB: Database '{test_db_name}' already exists")
        finally:
            await admin_engine.dispose()

        # Create engine with postgres
        engine = create_async_engine(
            test_db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,
        )

        # Create all tables using a more robust approach
        conn = await engine.connect()
        try:
            # Drop all tables first to avoid enum conflicts
            await conn.run_sync(Base.metadata.drop_all)
            # Drop any remaining enum types that might persist
            await conn.execute(
                text("""
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (
                        SELECT typname, typnamespace
                        FROM pg_type
                        WHERE typtype = 'e'
                        AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    ) LOOP
                        EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
                    END LOOP;
                END $$;
                """)
            )
            # Then create all tables
            await conn.run_sync(Base.metadata.create_all)
            # Commit the transaction to ensure tables are created
            await conn.commit()
        finally:
            await conn.close()
    else:
        # Local mode: use SQLite in-memory database
        print("TEST DB: Using SQLite in-memory database (no postgres required)")
        test_db_url = "sqlite+aiosqlite:///:memory:"

        # Create engine with SQLite
        engine = create_async_engine(
            test_db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Enable foreign key support for SQLite
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Create all tables for SQLite
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up - dispose engine and drop test database (postgres only)
    try:
        # Close all connections in the pool
        await engine.dispose()
        # Force cleanup of any remaining connections
        await asyncio.sleep(0.01)  # Brief pause for async cleanup
    except Exception as e:
        print(f"Warning: Error disposing test engine: {e}")
        # Force cleanup by closing all connections
        await asyncio.sleep(0.01)  # Give time for async cleanup

    # Drop the test database after tests complete (postgres only)
    if database_url_env:
        from sqlalchemy import text
        from sqlalchemy.engine.url import make_url

        url_obj = make_url(test_db_url)
        admin_db_url = url_obj.set(database="postgres")

        admin_engine = create_async_engine(admin_db_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin_engine.connect() as conn:
                # Terminate any active connections to the test database
                await conn.execute(
                    text("""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :db_name
                        AND pid <> pg_backend_pid()
                    """),
                    {"db_name": test_db_name},
                )

                # Drop test database
                print(f"TEST DB: Dropping database '{test_db_name}'")
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
                print(f"TEST DB: Database '{test_db_name}' dropped successfully")
        except Exception as e:
            print(f"TEST DB: Warning - could not drop database '{test_db_name}': {e}")
        finally:
            await admin_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    """
    Create database session for testing with transaction rollback.

    Uses nested transactions (savepoints) to isolate each test.
    After the test completes, all changes are rolled back.
    This follows the AGENTS.md requirement to use transaction rollback instead of dropping tables.
    """
    # Create a connection for the test
    connection = await async_engine.connect()

    # Start a transaction
    transaction = await connection.begin()

    # Create session bound to this connection
    async_session_maker = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_maker()

    # Start a nested transaction (savepoint)
    await session.begin_nested()

    # Setup automatic savepoint recreation on commit
    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    # Rollback everything
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """
    Create database session for testing with transaction rollback.

    Alternative naming convention for test session fixtures.
    Uses the same transaction rollback pattern as async_session.
    """
    # Create a connection for the test
    connection = await async_engine.connect()

    # Start a transaction
    transaction = await connection.begin()

    # Create session bound to this connection
    async_session_maker = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_maker()

    # Start a nested transaction (savepoint)
    await session.begin_nested()

    # Setup automatic savepoint recreation on commit
    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    # Rollback everything
    await session.close()
    await transaction.rollback()
    await connection.close()
