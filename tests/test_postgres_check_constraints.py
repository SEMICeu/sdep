#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "psycopg2-binary>=2.9.10",
#     "sqlalchemy>=2.0.36",
# ]
# ///

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from sqlalchemy import (
    URL,
    Column,
    DateTime,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

EXPECTED_ALEMBIC_REVISION = "006"

metadata = MetaData()

alembic_version = Table(
    "alembic_version",
    metadata,
    Column("version_num", String),
)

competent_authority = Table(
    "competent_authority",
    metadata,
    Column("id", Integer),
    Column("competent_authority_id", String),
    Column("competent_authority_name", String),
    Column("client_id", String),
)

platform = Table(
    "platform",
    metadata,
    Column("id", Integer),
    Column("platform_id", String),
    Column("platform_name", String),
    Column("client_id", String),
)

area = Table(
    "area",
    metadata,
    Column("id", Integer),
    Column("area_id", String),
    Column("area_name", String),
    Column("regulation", String),
    Column("competent_authority_id", Integer),
    Column("filename", String),
    Column("filedata", LargeBinary),
    Column("created_at", DateTime(timezone=True)),
)

activity = Table(
    "activity",
    metadata,
    Column("activity_id", String),
    Column("activity_name", String),
    Column("status", String),
    Column("platform_id", Integer),
    Column("area_id", Integer),
    Column("url", String),
    Column("address_thoroughfare", String),
    Column("address_locator_designator_number", Integer),
    Column("address_locator_designator_letter", String),
    Column("address_post_code", String),
    Column("address_post_name", String),
    Column("address_full_address", String),
    Column("registration_number", String),
    Column("number_of_guests", Integer),
    Column("country_of_guests", postgresql.ARRAY(String)),
    Column("temporal_start_date_time", DateTime(timezone=True)),
    Column("temporal_end_date_time", DateTime(timezone=True)),
)


@dataclass
class TestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        print(f"Error: {name} environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return value


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg2",
        database=env("POSTGRES_DB_NAME"),
        host=env("POSTGRES_HOST", "localhost"),
        password=env("POSTGRES_DB_PASSWORD"),
        port=int(env("POSTGRES_PORT", "5432")),
        username=env("POSTGRES_DB_USER"),
    )


def mark(stats: TestStats, ok: bool, passed_message: str, failed_message: str) -> None:
    stats.total += 1
    if ok:
        stats.passed += 1
        print(passed_message)
    else:
        stats.failed += 1
        print(failed_message)


def expect_integrity_error(connection, stats: TestStats, name: str, statement) -> None:
    try:
        with connection.begin_nested():
            connection.execute(statement)
    except IntegrityError as exc:
        constraint_name = getattr(getattr(exc, "orig", None), "diag", None)
        detail = getattr(constraint_name, "constraint_name", None)
        suffix = f" ({detail})" if detail else ""
        mark(
            stats,
            True,
            f"{name}: passed, PostgreSQL rejected the row{suffix}",
            "",
        )
    else:
        mark(stats, False, "", f"{name}: failed, PostgreSQL accepted invalid data")


def main() -> int:
    engine = create_engine(database_url(), pool_pre_ping=True)
    stats = TestStats()

    with engine.begin() as connection:
        revision = connection.execute(
            select(alembic_version.c.version_num)
        ).scalar_one()
        if revision != EXPECTED_ALEMBIC_REVISION:
            raise AssertionError(
                "Expected PostgreSQL database at Alembic revision "
                f"{EXPECTED_ALEMBIC_REVISION}, got {revision}"
            )

        print(f"Testing PostgreSQL CHECK constraints at revision {revision}")
        print()

        # This test commits its seed rows, so clean up any left over from an
        # earlier run to keep it idempotent against a persistent database
        # (FK order: activity -> area -> platform/competent_authority).
        connection.execute(
            delete(area).where(
                area.c.area_id == "sdep-test-area-check-constraints"
            )
        )
        connection.execute(
            delete(platform).where(
                platform.c.client_id == "sdep-test-platform-client"
            )
        )
        connection.execute(
            delete(competent_authority).where(
                competent_authority.c.client_id == "sdep-test-ca-client"
            )
        )

        competent_authority_id = connection.execute(
            insert(competent_authority)
            .values(
                competent_authority_id="sdep-test-ca-check-constraints",
                competent_authority_name="SDEP Test CA",
                client_id="sdep-test-ca-client",
            )
            .returning(competent_authority.c.id)
        ).scalar_one()
        platform_id = connection.execute(
            insert(platform)
            .values(
                platform_id="sdep-test-platform-check-constraints",
                platform_name="SDEP Test Platform",
                client_id="sdep-test-platform-client",
            )
            .returning(platform.c.id)
        ).scalar_one()
        area_id = connection.execute(
            insert(area)
            .values(
                area_id="sdep-test-area-check-constraints",
                area_name="SDEP Test Area",
                regulation="activity",
                competent_authority_id=competent_authority_id,
                filename="area.zip",
                filedata=b"zip",
            )
            .returning(area.c.id)
        ).scalar_one()

        expect_integrity_error(
            connection,
            stats,
            "Invalid areaId",
            insert(area).values(
                area_id="invalid area id",
                area_name="Invalid Area",
                regulation="activity",
                competent_authority_id=competent_authority_id,
                filename="area.zip",
                filedata=b"zip",
            ),
        )

        # Partial unique indexes: at most one current row per owner identity.
        expect_integrity_error(
            connection,
            stats,
            "Second current platform for same client_id",
            insert(platform).values(
                platform_id="sdep-test-platform-duplicate-current",
                platform_name="SDEP Test Platform Duplicate",
                client_id="sdep-test-platform-client",
            ),
        )
        expect_integrity_error(
            connection,
            stats,
            "Second current competent_authority for same client_id",
            insert(competent_authority).values(
                competent_authority_id="sdep-test-ca-duplicate-current",
                competent_authority_name="SDEP Test CA Duplicate",
                client_id="sdep-test-ca-client",
            ),
        )
        expect_integrity_error(
            connection,
            stats,
            "Second current area for same (area_id, competent_authority_id)",
            # Distinct created_at so the (area_id, ca, created_at) UNIQUE
            # constraint is satisfied and only the partial unique index on the
            # current row can reject this (now() is constant within a transaction).
            insert(area).values(
                area_id="sdep-test-area-check-constraints",
                area_name="SDEP Test Area Duplicate",
                regulation="activity",
                competent_authority_id=competent_authority_id,
                filename="area.zip",
                filedata=b"zip",
                created_at="2030-01-01T00:00:00+00:00",
            ),
        )

        base_activity = {
            "activity_id": "sdep-test-activity-check-constraints",
            "activity_name": "Invalid Activity",
            "status": "finished",
            "platform_id": platform_id,
            "area_id": area_id,
            "url": "http://example.com/listing",
            "address_thoroughfare": "Test Street",
            "address_locator_designator_number": 1,
            "address_locator_designator_letter": "A",
            "address_post_code": "1234AB",
            "address_post_name": "Test City",
            "address_full_address": "Test Street 1, 1234AB Test City",
            "registration_number": "REG-1",
            "number_of_guests": 1,
            "country_of_guests": ["NLD"],
            "temporal_start_date_time": "2025-01-01T00:00:00+00:00",
            "temporal_end_date_time": "2025-01-02T00:00:00+00:00",
        }
        invalid_cases = [
            ("Invalid activityId", {"activity_id": "invalid activity id"}),
            (
                "Invalid temporal order",
                {
                    "temporal_start_date_time": "2025-01-02T00:00:00+00:00",
                    "temporal_end_date_time": "2025-01-01T00:00:00+00:00",
                },
            ),
            (
                "startDatetime before 2025",
                {"temporal_start_date_time": "2024-12-31T00:00:00+00:00"},
            ),
            (
                "Non-alphabetic locatorDesignatorLetter",
                {"address_locator_designator_letter": "A1"},
            ),
        ]
        for name, overrides in invalid_cases:
            expect_integrity_error(
                connection,
                stats,
                name,
                insert(activity).values(base_activity | overrides),
            )

    print()
    print(f"Test results: {stats.passed}/{stats.total} passed")
    if stats.failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
