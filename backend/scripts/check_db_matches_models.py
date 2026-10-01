"""Check that the migrated PostgreSQL schema matches the models, where Alembic cannot.

`alembic check` (run by `make upgrade`) compares tables, columns, indexes and unique
constraints, but not CHECK constraints, nor the WHERE clause of a partial index.
This compares both: CHECK constraints by name, partial-index predicates by text.
"""

from __future__ import annotations

import re
import sys

from app.config import settings
from app.db.config import Base
from app.models import *  # noqa: F403 (registers every table on Base.metadata)
from sqlalchemy import URL, CheckConstraint, Index, create_engine, text


def _normalize(predicate: str) -> str:
    """Compare predicates without the parentheses and spacing PostgreSQL adds."""
    return re.sub(r"[()\s]", "", predicate).lower()


def _model_checks() -> set[tuple[str, str]]:
    """(table, name) of every CHECK constraint that PostgreSQL gets."""
    checks = set()
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and isinstance(
                constraint.name, str
            ):
                checks.add((table.name, constraint.name))
    return checks


def _model_predicates() -> dict[str, str]:
    """Index name -> normalized WHERE clause, for every partial index."""
    predicates = {}
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            where = index.dialect_options["postgresql"].get("where")
            if isinstance(index, Index) and where is not None and index.name:
                predicates[str(index.name)] = _normalize(str(where))
    return predicates


def main() -> int:
    url = URL.create(
        "postgresql+psycopg",
        database=settings.POSTGRES_DB_NAME,
        host=settings.POSTGRES_HOST,
        password=settings.POSTGRES_DB_PASSWORD,
        port=settings.POSTGRES_PORT,
        username=settings.POSTGRES_DB_USER,
    )
    with create_engine(url).connect() as connection:
        db_checks = {
            (str(table), str(name))
            for table, name in connection.execute(
                text(
                    "SELECT conrelid::regclass, conname FROM pg_constraint "
                    "WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
                )
            )
        }
        db_predicates = {
            str(name): _normalize(str(definition).split(" WHERE ", 1)[1])
            for name, definition in connection.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexdef LIKE '% WHERE %'"
                )
            )
        }

    # The first migrations named constraints through the "chk_<table>_" convention
    # (see alembic/env.py), later ones kept the model name as is. Both are a match.
    def in_db(table: str, name: str) -> bool:
        return (table, name) in db_checks or (table, f"chk_{table}_{name}") in db_checks

    model_checks = _model_checks()
    missing = sorted(f"{t}.{n}" for t, n in model_checks if not in_db(t, n))
    known = {(t, n) for t, n in model_checks} | {
        (t, f"chk_{t}_{n}") for t, n in model_checks
    }
    extra = sorted(f"{t}.{n}" for t, n in db_checks - known)

    model_predicates = _model_predicates()
    predicate_drift = sorted(
        f"{name}: model '{where}', database '{db_predicates.get(name)}'"
        for name, where in model_predicates.items()
        if db_predicates.get(name) != where
    )
    predicate_extra = sorted(set(db_predicates) - set(model_predicates))

    problems = [
        *(f"CHECK constraint in the models, not in the database: {m}" for m in missing),
        *(f"CHECK constraint in the database, not in the models: {e}" for e in extra),
        *(f"Partial index predicate differs: {d}" for d in predicate_drift),
        *(
            f"Partial index in the database, not in the models: {e}"
            for e in predicate_extra
        ),
    ]
    for problem in problems:
        print(f"❌ {problem}")
    if problems:
        return 1
    print(
        f"✅ {len(model_checks)} CHECK constraints and "
        f"{len(model_predicates)} partial-index predicates match the models"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
