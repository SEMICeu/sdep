<h1>Database Dialects</h1>

This document describes SQLite/PostgreSQL compatibility for the SDEP application.

For architecture and request flow, see [Technical Architecture](./ARCHITECTURE_TECH.md). \
For the internal data model, see [Data Model](./DATAMODEL.md).

<h2>Table of Contents</h2>

- [SQLite vs PostgreSQL](#sqlite-vs-postgresql)
- [Dialect Differences](#dialect-differences)
- [TypeDecorators](#typedecorators)
- [PostgreSQL-Specific Constraints](#postgresql-specific-constraints)
- [Porting Checklist](#porting-checklist)

---

## SQLite vs PostgreSQL

The internal data model targets **PostgreSQL** as the production database. **SQLite** is used for unit tests (in-memory) to keep the test cycle fast and self-contained.

**Unit tests** (`backend/tests/`) automatically switch to an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) when no `DATABASE_URL` environment variable is set. This lets developers run unit tests without PostgreSQL installed or running.

**Integration tests** (`tests/`) and **Production** both use PostgreSQL (`postgresql+asyncpg`) configured via environment variables (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB_NAME`, etc.).

|                 | Production | Integration tests (`tests/`) | Unit tests (`backend/tests/`) |
| --------------- | ---------- | ---------------------------- | ----------------------------- |
| **Database**    | PostgreSQL | PostgreSQL                   | SQLite (in-memory)            |
| **Trigger**     | always     | always                       | `DATABASE_URL` not set        |
| **Persistence** | persistent | persistent                   | ephemeral (per test)          |
| **Dependency**  | `asyncpg`  | `asyncpg`                    | `aiosqlite` (dev only)        |

## Dialect Differences

SQLAlchemy abstracts most of the differences, but a few PostgreSQL-specific types and constructs require dialect-aware handling to keep both engines green.

| Concern                                        | PostgreSQL                                                        | SQLite (tests)                                                |
| :--------------------------------------------- | :---------------------------------------------------------------- | :------------------------------------------------------------ |
| **Enum (`regulation`)**                        | Native `ENUM` type via `CREATE TYPE`                              | Emulated as `VARCHAR` with a `CHECK (col IN (...))`           |
| **String array (`countryOfGuests`)**           | Native `ARRAY(String)`                                            | Emulated as JSON text via custom `StringArray` type decorator |
| **Functional IDs (`areaId`, `activityId`, …)** | Stored as `VARCHAR(64)` deliberately, not `UUID` - see note below | Stored as `VARCHAR(64)`                                       |
| **`largeBinary` (`filedata`)**                 | `BYTEA`                                                           | `BLOB`                                                        |
| **`timestamptz` (`createdAt`, `endedAt`)**     | `TIMESTAMP WITH TIME ZONE`                                        | `TEXT` (ISO-8601)                                             |
| **`func.now()` defaults**                      | `now()` (transaction time)                                        | `CURRENT_TIMESTAMP`                                           |
| **CHECK constraints**                          | Fully supported                                                   | Fully supported                                               |
| **`ddl_if(dialect=...)`**                      | Used to gate PG-only DDL                                          | Skipped on SQLite                                             |

## TypeDecorators

Where a PostgreSQL-only type has no equivalent in another engine, the project bridges the gap with a custom `TypeDecorator` instead of branching the model layer.

- The `StringArray` decorator in `app/models/types.py` is the canonical example
- It stores a `list[str]` as a native PostgreSQL `ARRAY(String)` in production and as JSON text in SQLite, transparently to the rest of the code
- The same pattern can be reused for any other type that needs an engine-specific representation - keep the decorator next to the model layer so all dialect awareness lives in one place

For built-in enum support, prefer SQLAlchemy's `Enum(..., native_enum=True)` over a custom decorator: it emits `CREATE TYPE` on engines that have native enums and falls back to `VARCHAR` + `CHECK` elsewhere, with no application-level branching.

**Why functional IDs are `VARCHAR(64)` and not `UUID`**

Clients are allowed to submit their own functional IDs (alphanumeric with hyphens, ≤ 64 chars, e.g. `"amsterdam-area0363"`). These are not required to be UUIDs, so the column type must accept arbitrary short strings.

## PostgreSQL-Specific Constraints

Because some CHECK constraints rely on PostgreSQL-specific SQL (e.g. `array_length`) and cannot run on SQLite, they are declared PostgreSQL-only in both the model (`.ddl_if(dialect="postgresql")`) and the Alembic migration (wrapped in `if is_postgres:`); the DDL is skipped under SQLite, so enforcement falls back to the application layers above the DB:

- **Model** (`backend/app/models/activity.py`) - `CheckConstraint("number_of_guests = array_length(country_of_guests, 1)", name="ck_activity_guests_cardinality").ddl_if(dialect="postgresql")`
- **Migration** (`backend/alembic/versions/001_initial.py`) - the `create_check_constraint(...)` call is inside an `if is_postgres:` guard
- **Pydantic fallback** - `ActivityRequest.validate_guest_cardinality` (`@model_validator(mode="after")`) rejects mismatched requests, covering every API/bulk path including SQLite-backed unit tests
- **Factory fallback** - `ActivityFactory.country_of_guests = LazyAttribute(lambda o: ["NLD"] * o.number_of_guests)` guarantees consistency for CRUD-level tests that call `activity.create()` directly and bypass Pydantic

A direct CRUD call on SQLite with manually mismatched lists would not be caught by either DB or Pydantic; tests must route through Pydantic or use the factory to stay consistent.

## Porting Checklist

1. **Driver** - verify SQLAlchemy has a working async driver for the target engine, and that it is compatible with the project's SQLAlchemy version.
2. **Dialect-specific imports** - audit the model layer for `postgresql.*` (or any other dialect-specific) imports; replace them with a `TypeDecorator` (see `app/models/types.py`) so the same model definition works on every engine.
3. **Native types vs. fallbacks** - review the dialect differences table above and confirm each "PostgreSQL" cell has a working equivalent on the target engine. For types without a native equivalent, decide between (a) a `TypeDecorator` that emulates the type, or (b) a normalized child table.
4. **Default-value functions** - confirm that any `server_default` / `func.*` calls resolve to a valid expression on the target engine (timestamps, UUIDs, sequence-style identifiers).
5. **Migrations** - re-run the Alembic migrations against a clean instance of the target engine. Pay attention to operations that PostgreSQL allows but other engines do not (e.g. creating an enum type, transactional DDL, deferred constraints) and gate them with `op.get_bind().dialect.name` or `ddl_if(dialect=...)`.
6. **Constraints** - verify that CHECK, UNIQUE, and FOREIGN KEY constraints are enforced (some older engine versions parse but ignore CHECK constraints).
7. **Transaction & isolation semantics** - test concurrency-sensitive code paths (versioning, soft-delete, bulk insert) on a real instance of the target engine; isolation defaults and locking behaviour vary considerably between engines.
8. **Run the full test suite** - point the test config at a real instance of the target engine and run `make test`. SQLite-only validation is not enough to catch dialect-specific behaviour.
