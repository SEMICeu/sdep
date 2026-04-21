<h1>Technical Architecture</h1>

This document provides an overview of the SDEP (Single Digital Entry Point) technical architecture:

- [Overview](#overview)
- [Technology Stack](#technology-stack)
  - [Backend](#backend)
  - [Infrastructure](#infrastructure)
  - [Development Tools](#development-tools)
- [Directory Structure](#directory-structure)
- [Backend Architecture](#backend-architecture)
  - [API Layer (`app/api/`)](#api-layer-appapi)
  - [Schemas Layer (`app/schemas/`)](#schemas-layer-appschemas)
  - [Service Layer (`app/services/`)](#service-layer-appservices)
  - [CRUD Layer (`app/crud/`)](#crud-layer-appcrud)
  - [Models Layer (`app/models/`)](#models-layer-appmodels)
- [Request Flow](#request-flow)
- [Key Endpoints](#key-endpoints)
  - [Authentication](#authentication)
  - [Competent Authority (CA) - Requires `sdep_ca` role](#competent-authority-ca-requires-sdep_ca-role)
  - [Short-Term Rental Platform (STR) - Requires `sdep_str` role](#short-term-rental-platform-str-requires-sdep_str-role)
  - [Health](#health)
- [Security](#security)
  - [Audit Logging](#audit-logging)
  - [Security Headers](#security-headers)
  - [Middleware Ordering](#middleware-ordering)
- [Transaction Management](#transaction-management)
- [Validation](#validation)
  - [Layers](#layers)
  - [Functional IDs (general)](#functional-ids-general)
  - [Functional IDs (user-supplied)](#functional-ids-user-supplied)
  - [Functional IDs (JWT-provisioned)](#functional-ids-jwt-provisioned)
- [Exception Handling](#exception-handling)
- [Bulk updates](#bulk-updates)
  - [Approach](#approach)
  - [Validation](#validation-1)
  - [Validation flow (4 steps)](#validation-flow-4-steps)
  - [HTTP status codes (bulk-specific)](#http-status-codes-bulk-specific)
  - [Design decisions](#design-decisions)
- [Development Workflow](#development-workflow)
- [Testing Strategy](#testing-strategy)
  - [Unit Tests (`backend/tests/`)](#unit-tests-backendtests)
  - [Integration Tests (`tests/`)](#integration-tests-tests)
  - [Performance Tests (`tests/perf/`)](#performance-tests-testsperf)
- [SQLite vs PostgreSQL](#sqlite-vs-postgresql)
- [Key Configuration Files](#key-configuration-files)

---

## Overview

SDEP is a FastAPI-based REST API that enables:

- Competent Authorities (CA) to register regulated areas with geospatial data
- Short-Term Rental platforms (STR) to query regulated areas and submit rental activities
- Competent Authorities (CA) to query rental activities
- Compliance with EU Regulation 2024/1028

**Production (NL):** https://sdep.gov.nl/api/v0/docs

- This is the reference implementation for this repo

---

## Technology Stack

### Backend
- **Python:** 3.13+
- **Framework:** FastAPI 0.115+
- **ORM:** SQLAlchemy 2.0+ (async)
- **Migrations:** Alembic
- **Validation:** Pydantic 2.10+
- **Authentication:** OAuth2 Client Credentials via Keycloak
- **Server:** Uvicorn

### Infrastructure
- **Container Platform:** Docker + Docker Compose
- **Identity Provider:** Keycloak (OAuth2/OIDC)
- **Database:** PostgreSQL 15+
- **Package Manager:** uv (Python)

### Development Tools
- **Linting:** Ruff
- **Type Checking:** Pyright
- **Testing:** pytest (with pytest-asyncio, pytest-xdist for parallel execution)
- **Pre-commit:** Hooks for code quality
- **CI/CD:** GitLab CI or otherwise (out of scope for this project)

---

## Directory Structure

```
sdep-app/
├── backend/                                    # Python FastAPI application
│   ├── app/                                    # Application code
│   │   ├── api/                                # API layer (routers, endpoints)
│   │   │   ├── common/                         # Shared API components (routers, openapi, security)
│   │   │   │   ├── routers/                    # API routers
│   │   │   │   │   ├── auth.py                 # Authentication router
│   │   │   │   │   ├── ca_activities.py        # CA activity endpoints
│   │   │   │   │   ├── ca_areas.py             # CA area endpoints
│   │   │   │   │   ├── health.py               # Health check router
│   │   │   │   │   ├── ping.py                 # Ping endpoint
│   │   │   │   │   ├── str_activities_bulk.py  # STR bulk activity endpoints
│   │   │   │   │   └── str_areas.py            # STR area endpoints
│   │   │   │   ├── auth_dependencies.py        # Shared auth/role dependencies
│   │   │   │   ├── exception_handlers.py
│   │   │   │   ├── openapi.py
│   │   │   │   └── security.py
│   │   │   ├── common_app.py                   # Version-independent sub-app (health)
│   │   │   └── v0/                             # API version 0
│   │   │       ├── main.py                     # API v0 entry point
│   │   │       └── security.py                 # v0 security configuration
│   │   ├── crud/                               # Database operations (CRUD)
│   │   │   ├── activity.py
│   │   │   ├── area.py
│   │   │   ├── competent_authority.py
│   │   │   └── platform.py
│   │   ├── db/                                 # Database configuration
│   │   │   └── config.py                       # Database session management
│   │   ├── exceptions/                         # Custom exceptions
│   │   │   ├── auth.py                         # Authentication exceptions
│   │   │   ├── base.py                         # Base exception classes
│   │   │   ├── business.py                     # Business logic exceptions
│   │   │   ├── handlers.py                     # Exception handlers
│   │   │   ├── infrastructure.py               # Infrastructure exceptions (DB, auth server)
│   │   │   └── validation.py                   # Validation exceptions
│   │   ├── models/                             # SQLAlchemy ORM models
│   │   │   ├── activity.py
│   │   │   ├── address.py
│   │   │   ├── area.py
│   │   │   ├── audit_log.py                    # Audit log record
│   │   │   ├── competent_authority.py
│   │   │   ├── platform.py
│   │   │   ├── temporal.py
│   │   │   └── types.py                        # Dialect-aware TypeDecorators (e.g. StringArray)
│   │   ├── schemas/                            # Pydantic schemas (request/response)
│   │   │   ├── activity.py
│   │   │   ├── activity_bulk.py
│   │   │   ├── area.py
│   │   │   ├── auth.py
│   │   │   ├── common.py                       # Shared types: FunctionalId, validate_functional_id()
│   │   │   ├── error.py
│   │   │   └── health.py
│   │   ├── security/                           # Security utilities
│   │   │   ├── audit.py                        # Audit logging middleware
│   │   │   ├── audit_retention.py              # Background audit log cleanup
│   │   │   └── headers.py                      # Security headers
│   │   ├── services/                           # Business logic layer
│   │   │   ├── activity.py
│   │   │   ├── activity_bulk.py
│   │   │   └── area.py
│   │   ├── config.py                           # Application configuration
│   │   ├── enums.py                            # Shared enumerations (e.g. Regulation)
│   │   └── main.py                             # Application entry point
│   ├── alembic/                                # Database migrations
│   │   ├── env.py                              # Alembic environment config
│   │   └── versions/                           # Migration scripts
│   │       ├── 001_initial.py                  # Initial migration
│   │       ├── 002_audit_log.py                # Audit log table
│   │       ├── 003_address_inspire.py          # INSPIRE/STR-AP address field rename
│   │       └── 004_area_regulation.py          # Area regulation enum column
│   ├── tests/                                  # Unit tests (mirrors app/ structure)
│   │   ├── api/                                # API layer tests
│   │   ├── crud/                               # CRUD layer tests
│   │   ├── fixtures/                           # Test fixtures and factories
│   │   ├── security/                           # Security tests
│   │   ├── services/                           # Service layer tests
│   │   └── conftest.py                         # pytest configuration
│   ├── alembic.ini                             # Alembic configuration
│   ├── Dockerfile                              # Backend container image
│   ├── Makefile                                # Backend-specific make targets
│   ├── pyproject.toml                          # Python project configuration (uv)
│   └── uv.lock                                 # Locked dependencies
│
├── tests/                                      # Integration tests + performance tests
│   ├── lib/                                    # Test library utilities
│   │   └── create_fixture_areas.sh             # Area fixture creation
│   ├── perf/                                   # Performance tests (Locust)
│   │   └── locustfile.py                       # Bulk activity load test
│   ├── test_auth_client.sh                     # OAuth2 token acquisition utility
│   ├── test_auth_credentials.sh                # Test client credentials flow
│   ├── test_auth_headers.sh                    # Security headers compliance
│   ├── test_auth_unauthorized.sh               # Test unauthorized access rejection
│   ├── test_ca_activities.sh                   # Test CA activity endpoints
│   ├── test_ca_areas.sh                        # Test CA area submission
│   ├── test_health_ping.sh                     # Health check tests
│   ├── test_str_activities_bulk.sh             # Test STR bulk activity submission
│   └── test_str_areas.sh                       # Test STR area query endpoints
│
├── keycloak/                                   # Keycloak config
│   ├── add-realm-admin.sh                      # Create realm admin user
│   ├── add-realm-machine-clients.sh            # Configure OAuth2 machine clients
│   ├── add-realm-roles.sh                      # Configure roles
│   ├── add-realm.sh                            # Initialize realm
│   ├── get-client-secret.sh                    # Retrieve client secret
│   ├── machine-clients.yaml                    # Machine client definitions (CA, STR)
│   ├── roles.yaml                              # Role definitions
│   └── wait.sh                                 # Wait for Keycloak startup
│
├── postgres/                                   # PostgreSQL initialization
│   ├── clean-app.sql                           # Database cleanup
│   ├── clean-testrun.sql                       # Test run cleanup
│   ├── count-app.sql                           # Row count queries
│   ├── init-keycloak.sql                       # Keycloak database setup
│   └── init-app.sql                            # SDEP database setup
│
├── test-data/                                  # Test data for integration tests
│   ├── shapefiles/                             # Shapefile test data (zipped)
│   ├── 01-competent-authority.sql              # Competent authority fixtures
│   ├── 02-area-generated.sql                   # Generated area data
│   └── generate-area-sql.sh                    # Area data generator script
│
├── docs/                                       # Documentation
│   ├── API.md                                  # API documentation
│   ├── ARCHITECTURE_TECH.md                    # Architecture overview (this file)
│   ├── DATAMODEL.md                            # Data model documentation
│   ├── INTEGRATION_TESTS.md                    # Integration test documentation
│   ├── LISTING_ACTIVITY.md                     # Activity listing documentation
│   ├── PERFORMANCE_TESTS.md                    # Performance test documentation
│   ├── PRE.md                                  # Pre-conditions documentation
│   ├── SECURITY.md                             # Security documentation
│   ├── WOW.md                                  # Ways of working
│   └── diagrams/                               # Architecture and data model diagrams
│       ├── ACTIVITY.excalidraw
│       ├── ACTIVITY.svg
│       ├── ACTIVITYFLOW.excalidraw
│       ├── ACTIVITYFLOW.svg
│       ├── ARCHITECTURE_FUNC.png
│       ├── DATAMODEL.excalidraw
│       ├── DATAMODEL.svg
│       ├── LISTING.excalidraw
│       ├── LISTING.svg
│       ├── LISTINGFLOW.excalidraw
│       └── LISTINGFLOW.svg
│
├── scripts/                                    # Utility scripts
│   ├── run-tests.sh                            # Integration test runner
│   └── run-tests-perf.sh                       # Performance test runner (Locust)
│
├── .env                                        # Environment variables
├── .gitignore                                  # Git ignore rules
├── .gitlab-ci.yml                              # GitLab CI/CD configuration
├── CHANGELOG.md                                # Changelog
├── docker-compose.yml                          # Multi-container orchestration
├── LICENSE.md                                  # EUPL License
├── Makefile                                    # Root-level make targets
└── README.md                                   # Quick start guide
```

---

## Backend Architecture

The backend follows a **layered architecture** pattern:

### API Layer (`app/api/`)
- HTTP request/response handling
- Route definitions and parameter validation
- Authentication/authorization enforcement
- Transaction boundary via `get_async_db` dependency (auto-commit on success, rollback on exception)

### Schemas Layer (`app/schemas/`)
- Pydantic models for request/response validation
- Data serialization/deserialization
- camelCase aliases for JSON API (e.g. `activityId`, `areaId`, `postCode`)
- Validation (Layer 1: type/format validation)

### Service Layer (`app/services/`)
- Business logic implementation
- Validation (Layer 2: business rules, e.g. area exists, platform lookup/creation)
- Raises `ApplicationValidationError` for domain-level errors (e.g. area not found)
- No transaction management (delegated to API layer)

### CRUD Layer (`app/crud/`)
- Database operations (Create, Read, Update, Delete)
- Data access abstraction
- SQLAlchemy query construction
- Uses flush (not commit) - defers transaction control to upper layers

### Models Layer (`app/models/`)
- SQLAlchemy ORM models
- Database table definitions
- Relationships and constraints
- Includes `audit_log.py` for the audit trail (see [Security > Audit Logging](#audit-logging))

For key patterns, see also [Datamodel](./DATAMODEL.md), [Security](./SECURITY.md), and [API](./API.md).

---

## Request Flow

```
POST /str/activities/bulk (JSON body with activities array)
  │
  ├── API Layer (str_activities_bulk.py)
  │   ├── verify_bearer_token() → auth checks (roles, claims)
  │   ├── ActivityBulkRequest (Pydantic) → validates wrapper (min 1, max 1000)
  │   └── get_async_db → auto-commit/rollback transaction
  │
  ├── Service Layer (activity_bulk.py) - Application-First Validation
  │   ├── Step 1: Per-item Pydantic validation via TypeAdapter
  │   ├── Platform resolution (once per batch, version on name change only)
  │   ├── Intra-batch dedup (last-wins)
  │   ├── Step 2: RI check → single SELECT for area IDs → Python dict
  │   ├── Activity versioning → batch UPDATE (mark-as-ended)
  │   ├── Step 3: Bulk INSERT (single multi-row INSERT)
  │   └── Step 4: Build per-item OK/NOK feedback
  │
  ├── CRUD Layer (activity.py, area.py)
  │   └── flush (not commit)
  │
  └── Response: 201 (all OK) / 200 (partial) / 422 (all NOK)
       + ActivityBulkResponse (camelCase JSON)

POST /ca/areas (multipart/form-data: file + optional areaId, areaName)
  │
  ├── API Layer (ca_areas.py)
  │   ├── verify_bearer_token() → auth checks (roles, claims)
  │   ├── File validation (max 1 MiB)
  │   ├── areaId/areaName validation (pattern, length)
  │   └── get_async_db → auto-commit/rollback transaction
  │
  ├── Service Layer (area.py)
  │   ├── create_area(session, area_id, area_name, filename, filedata, ca_id, ca_name)
  │   ├── Lookup/create competent authority from JWT claims
  │   └── Create area via CRUD
  │
  ├── CRUD Layer (area.py)
  │   └── flush (not commit)
  │
  └── Response: 201 + AreaResponse (camelCase JSON)
```

---

## Key Endpoints

### Authentication
- `POST /api/v0/auth/token` - OAuth2 token endpoint

### Competent Authority (CA) - Requires `sdep_ca` role
- `POST /api/v0/ca/areas` - Submit a single area (multipart/form-data: file + optional areaId, areaName)
- `GET /api/v0/ca/areas` - List own areas (pagination: offset, limit)
- `GET /api/v0/ca/areas/count` - Count own areas
- `GET /api/v0/ca/areas/{areaId}` - Download shapefile for own area
- `DELETE /api/v0/ca/areas/{areaId}` - Delete (deactivate) an own area
- `GET /api/v0/ca/activities` - Query rental activities (pagination: offset, limit)
- `GET /api/v0/ca/activities/count` - Count activities

### Short-Term Rental Platform (STR) - Requires `sdep_str` role
- `GET /api/v0/str/areas` - List regulated areas (pagination: offset, limit)
- `GET /api/v0/str/areas/count` - Count areas
- `GET /api/v0/str/areas/{areaId}` - Download shapefile for area
- `POST /api/v0/str/activities/bulk` - Submit up to 1000 activities in bulk (JSON body)

### Health
- `GET /api/health` - Health check (unauthenticated)
- `GET /api/v0/ping` - Ping endpoint (authenticated)

## Security

- **Protocol:** OAuth2 Client Credentials flow
- **Identity Provider:** Keycloak
- **Token Type:** JWT Bearer tokens
- **Roles:**
  - `sdep_ca` - Competent Authority access
  - `sdep_str` - STR Platform access
  - `sdep_read` - Read operations
  - `sdep_write` - Write operations
- **JWT Claims:**
  - `client_id` - Maps to platform/competent authority functional ID
  - `client_name` - Maps to platform/competent authority name
  - `realm_access.roles` - Role-based authorization

### Audit Logging

**AuditLogMiddleware** (`security/audit.py`) tracks all API requests to the `audit_log` table:
- Records: request ID, client ID, etc.
- Skips low-value paths (health, docs, root)
- Extracts JWT claims without verification (auth happens in route dependencies)
- Writes records asynchronously to avoid blocking responses; audit failures never break the request

**Audit retention** (`security/audit_retention.py`) runs a background cleanup loop (started via lifespan) that periodically deletes audit log rows older than the configured retention period (`AUDITLOG_RETENTION` setting), processing in batches of 1000.

For details, see [Security](./SECURITY.md#audit-log).

### Security Headers

**SecurityHeadersMiddleware** (`security/headers.py`) adds OWASP-recommended security headers to all responses:
- `X-Frame-Options: DENY` - clickjacking protection
- `X-Content-Type-Options: nosniff` - MIME-sniffing protection
- `Content-Security-Policy` - XSS protection (optional, configurable)
- `Strict-Transport-Security` - HTTPS enforcement (optional, usually handled by reverse proxy)
- `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy` - cross-origin isolation
- `Permissions-Policy` - restrict browser features
- `Referrer-Policy: no-referrer` - prevent information leakage
- Strict `Cache-Control` for sensitive endpoints (auth, activities, areas)

### Middleware Ordering

Starlette processes middleware LIFO (last added = outermost = runs first). In `main.py`:
1. **SecurityHeadersMiddleware** (outermost) - added last, runs first
2. **AuditLogMiddleware** (inner) - added first, runs inside security headers

---

## Transaction Management

Two session factories handle different operation types:

| Dependency               | Session Type                | Transaction                                   | Used by        |
| ------------------------ | --------------------------- | --------------------------------------------- | -------------- |
| `get_async_db`           | Write (autoflush=True)      | Auto-commit on success, rollback on exception | POST endpoints |
| `get_async_db_read_only` | Read-only (autoflush=False) | No transaction overhead                       | GET endpoints  |

POST endpoints use `get_async_db` which wraps the entire request in a single transaction. If any error occurs, the entire operation is rolled back. On success, the transaction is committed automatically.

---

## Validation

Validation is distributed across three layers, each with a distinct responsibility.

### Layers

| Layer                             | Responsibility                                              | Mechanism                                           | Example                                                              |
| --------------------------------- | ----------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------- |
| **Schemas (Pydantic)**            | Syntax: types, formats, lengths, patterns                   | Pydantic `Field()` constraints and type annotations | `activityId` must match `^[A-Za-z0-9-]+$`, max 64 chars              |
| **Service**                       | Business rules: referential integrity, state checks         | Python logic, database lookups                      | Area must exist, deactivated entities cannot be resubmitted          |
| **Model (SQLAlchemy/PostgreSQL)** | Data integrity: uniqueness, foreign keys, check constraints | Database constraints, model defaults                | Unique constraint on `(area_id, competent_authority_id, created_at)` |

### Functional IDs (general)

All functional IDs conform to a single pattern defined in `app/schemas/common.py`:

```
^[A-Za-z0-9-]+$    (1–64 characters, alphanumeric with hyphens)
```

This pattern is expressed as two reusable types:

| Type                   | Base type     | Used for                                                                                         |
| ---------------------- | ------------- | ------------------------------------------------------------------------------------------------ |
| `FunctionalId`         | `str`         | IDs that **must** be present (references to existing entities, response fields, path parameters) |
| `OptionalFunctionalId` | `str \| None` | IDs that **may** be omitted (create inputs where the system generates a UUID if not provided)    |


### Functional IDs (user-supplied)

**Area and Activity functional IDs** are user-supplied.

These IDs are submitted by the caller in the request body or form fields and validated **declaratively by Pydantic** before the endpoint function body runs:

| Endpoint                    | Field                 | Type                   | Pydantic validates?                                       | When omitted                                                |
| --------------------------- | --------------------- | ---------------------- | --------------------------------------------------------- | ----------------------------------------------------------- |
| `POST /ca/areas`            | `areaId` (form field) | `OptionalFunctionalId` | Yes - `Annotated[OptionalFunctionalId, Form()]`           | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |
| `POST /str/activities/bulk` | `activityId` per item | `OptionalFunctionalId` | Yes - via `TypeAdapter(ActivityRequest)` in service layer | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |

**Why `POST /ca/areas` uses `Form()` instead of a JSON body** (see implementation):

- `POST /ca/areas` accepts **multipart/form-data** (required for file upload), so each field is an individual `Form()` parameter
  - The `Annotated[OptionalFunctionalId, Form()]` type annotation ensures Pydantic still validates the form field declaratively, just like JSON body fields
- `POST /str/activities/bulk` accepts a JSON body; per-item validation is done via `TypeAdapter(ActivityRequest)` in the service layer

### Functional IDs (JWT-provisioned)

**Platform and Competent Authority functional IDs** are provisioned from JWT.

These IDs are **not** supplied by the user in the request payload. They are extracted from the JWT token's `client_id` claim at the API layer and validated imperatively using `validate_functional_id()` from `app/schemas/common.py`.

This function checks the same pattern (`^[A-Za-z0-9-]+$`, 1–64 chars) and raises `ValueError` on mismatch, which the API layer converts to HTTP 422.

| Endpoint                    | Router                   | Extracted as             | Validated by               |
| --------------------------- | ------------------------ | ------------------------ | -------------------------- |
| `POST /ca/areas`            | `ca_areas.py`            | `competent_authority_id` | `validate_functional_id()` |
| `GET /ca/areas`             | `ca_areas.py`            | `competent_authority_id` | `validate_functional_id()` |
| `GET /ca/areas/count`       | `ca_areas.py`            | `competent_authority_id` | `validate_functional_id()` |
| `GET /ca/areas/{areaId}`    | `ca_areas.py`            | `competent_authority_id` | `validate_functional_id()` |
| `DELETE /ca/areas/{areaId}` | `ca_areas.py`            | `competent_authority_id` | `validate_functional_id()` |
| `GET /ca/activities`        | `ca_activities.py`       | `competent_authority_id` | `validate_functional_id()` |
| `GET /ca/activities/count`  | `ca_activities.py`       | `competent_authority_id` | `validate_functional_id()` |
| `POST /str/activities/bulk` | `str_activities_bulk.py` | `platform_id`            | `validate_functional_id()` |

**Why imperative, not declarative:** JWT claims are not part of the request body or form fields - they arrive via the `verify_bearer_token` dependency as a plain `dict`. Pydantic schema validation does not apply to them, so the API layer validates them explicitly before passing them to the service layer.

---

## Exception Handling

All exceptions are handled by global exception handlers defined in `app/exceptions/handlers.py` and registered in `app/api/common/exception_handlers.py`. For the complete list of HTTP status codes used by the API, see [HTTP status codes](API.md#http-status-codes).

The table below shows how application exceptions map to HTTP status codes:

| HTTP Status                 | Exception                             | Description                                                                                                   |
| --------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 400                         | `RequestValidationError`              | Invalid query parameters on a GET request (e.g. `offset=-1` or `limit=abc`)                                   |
| 400 / 401 / 403 / 404 / 422 | `HTTPException`                       | Missing/invalid token claims, missing roles, missing credentials, inline input validation, resource not found |
| 401                         | `InvalidTokenError`                   | Invalid token (subtype of AuthenticationError)                                                                |
| 401                         | `AuthenticationError`                 | Invalid or expired token                                                                                      |
| 403                         | `AuthorizationError`                  | Insufficient permissions                                                                                      |
| 404                         | `ResourceNotFoundError`               | Resource not found                                                                                            |
| 409                         | `DuplicateResourceError`              | Duplicate resource conflict                                                                                   |
| 422                         | `RequestValidationError`              | Invalid request body on a POST request (e.g. missing required field or wrong value type)                      |
| 422                         | `ApplicationValidationError`          | Business rule violations (e.g. start time later than end time is NOK )                                        |
| 500                         | `Exception`                           | Catch-all (unexpected code failure)                                                                           |
| 503                         | `DatabaseOperationalError`            | Database temporarily unavailable                                                                              |
| 503                         | `AuthorizationServerOperationalError` | Authorization server temporarily unavailable                                                                  |

---

## Bulk updates

The bulk endpoint `POST /str/activities/bulk` is the single entry point for all STR activity submissions.

### Approach

At high volumes (500K–4M records/day, ~6–46 records/second average), PostgreSQL is not the bottleneck - a standard Postgres instance can process thousands of transactions per second. The actual bottlenecks are:

1. **Network latency** - solved by batching 500–1000 items per API call
2. **Disk I/O (WAL pressure)** - solved by multi-row `INSERT ... VALUES` instead of individual inserts

Five implementation strategies were evaluated:

| Option | Strategy              | Validation   | Mechanism                                                                  | Verdict                      |
| :----- | :-------------------- | :----------- | :------------------------------------------------------------------------- | :--------------------------- |
| **1**  | Single, Sync          | Direct       | 1 request = 1 insert. Enormous network overhead.                           | Not recommended              |
| **2**  | Single, Async         | Direct       | `await session.add()`. No bulk advantage, high WAL pressure.               | N/A                          |
| **3**  | **Bulk, Sync**        | Direct (App) | API validates batch in Python. Writes "clean" data to DB in one go.        | **Best for direct feedback** |
| **4a** | Bulk, Async (Staging) | Deferred     | API writes raw JSON to an unlogged Postgres table. Worker validates later. | Best without extra infra     |
| **4b** | Bulk, Async (Queue)   | Deferred     | API puts batch on Redis/Kafka. Workers validate and write.                 | Best for scalability         |

**Option 3 (Bulk, Sync) is the chosen approach.** At this volume, the two async alternatives solve problems that do not apply here:

- **Async with staging table (4a):** defers validation to a background worker, which means the client does not get per-item OK/NOK feedback in the HTTP response. Adds operational complexity (worker process, polling/callback for results) without a performance need.
- **Async with queue (4b):** introduces additional infrastructure (Redis/Kafka + consumer workers). Justified only for extreme peak-absorption or cross-service fan-out, neither of which applies at this volume.

Synchronous bulk gives the client **immediate, per-item feedback** (OK/NOK with error reasons) in the same HTTP response, requires **no extra infrastructure** beyond the API and database, and keeps the architecture simple - validation and insert happen in one transaction with no background workers or message brokers.

### Validation

Instead of having the database check each record via savepoints, errors are caught in the application layer:

- Application-level Pydantic validation is **many times faster** than database savepoints
- **Horizontally scalable**: add more API nodes under load
- **Single reference query per batch** (not per record)
- Only "clean" (validated) data reaches the database
-  No savepoints or nested transactions needed, which avoids the overhead of extra database round-trips.

The wire contract (OpenAPI) and the runtime validation behavior are deliberately decoupled:

- **Contract (OpenAPI)** — `ActivityBulkRequest.activities` is typed concretely as `list[ActivityRequest]`, so the spec documents the full item shape instead of an untyped object
- **Runtime** — items are *not* validated at request-parse time. If Pydantic validated the whole list eagerly, one bad item would return HTTP 422 for the entire batch and the per-item OK/NOK flow would be unreachable.

Implementation:

- The field is declared as `list[SkipValidation[ActivityRequest]]`
  - `SkipValidation` keeps the declared type for JSON-schema generation but replaces the runtime validator with a pass-through
  - So items arrive at the service layer as raw dicts
  - Exactly what step 1 (`TypeAdapter(ActivityRequest).validate_python()` per item) expects
- Because `SkipValidation` makes FastAPI's model-discovery pass treat the field as a leaf, `ActivityRequest` is **not** auto-registered in `components.schemas`
  - FastAPI inlines its schema into `items`
  - A post-processing hook in `app/api/common/openapi.py` (`extract_bulk_activity_item_schema`) lifts the inlined schema out and replaces the inline with a `$ref` to `#/components/schemas/ActivityRequest`, restoring it as a reusable named component
  - This follows the same pattern already used in that file for renaming `Body_*` schemas

Result:

- The contract is schema-concrete and reusable
- Runtime behavior preserves per-item NOK feedback unchanged

### Validation flow (4 steps)

| Step                               | What                                                                                                                                                                                                                  | How                                                       |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **1. Pydantic Check**              | Validate each item individually against the ActivityRequest schema. Mark failed items as NOK with the error reason.                                                                                                   | `TypeAdapter(ActivityRequest).validate_python()` per item |
| **2. Referential Integrity Check** | For the remaining OK records: fetch all referenced area IDs in a single query. Store in a Python `dict` for O(1) lookup. Items with unknown `areaId` → NOK.                                                           | `SELECT area_id, id FROM area WHERE area_id IN (...)`     |
| **3. Bulk Insert**                 | For the remaining OK records: insert in a single database operation.                                                                                                                                                  | `session.execute(insert(Activity), list_of_valid_dicts)`  |
| **4. Feedback**                    | Return per-item OK/NOK response preserving original order, enriched with batch-item `status`, embedded `activity` (OK) or `errorMessages` array (NOK). The embedded activity also carries its own lifecycle `status`. | JSON response with summary counts                         |

**Motivation for step 2 after step 1:** \
Prevents unvalidated (untrusted) data from being used in database operations.

### HTTP status codes (bulk-specific)

| HTTP Status                   | When                                                                |
| ----------------------------- | ------------------------------------------------------------------- |
| **201 Created**               | All items created successfully (`failed == 0`)                      |
| **200 OK**                    | Partial success: some OK, some NOK (`succeeded > 0 AND failed > 0`) |
| **422 Unprocessable Content** | All items failed validation (`succeeded == 0`)                      |

### Design decisions

| #      | Decision                                                                                                                                                                                                          | Rationale                                                                                                                                                               |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | **Per-item Pydantic validation** - the request accepts raw dicts, each validated individually in the service layer                                                                                                | One invalid item should not block the other (999) items in the batch. If one item has a missing field, the rest are still processed.                                    |
| **D2** | **Intra-batch duplicates: last-wins** - when the same `activityId` appears multiple times in a single batch, only the last occurrence is processed; earlier occurrences receive NOK                               | Deterministic and predictable for clients. Avoids ambiguity about which version "wins".                                                                                 |
| **D3** | **Versioning: batch UPDATE before INSERT** - existing current versions in the database are marked as ended via a single batch `UPDATE ... WHERE activity_id IN (...)` before the bulk INSERT creates new versions | Consistent with single-endpoint versioning semantics, but uses batch operations (1 UPDATE + 1 INSERT) instead of per-item queries.                                      |
| **D4** | **Platform resolution: version only on name change** - platform is resolved once per batch; a new version is only created if the JWT claim (`client_name`) has changed                                            | Avoids unnecessary versioning churn when the same platform submits many batches with unchanged credentials.                                                             |
| **D5** | **Deactivated entities rejected** - if an `activityId` has been deactivated (all versions have `endedAt` set), submitting it again is rejected (NOK)                                                              | Prevents "resurrecting" soft-deleted entities. Consistent with single endpoint behavior.                                                                                |
| **D6** | **No `ON CONFLICT DO NOTHING`** - SDEP uses explicit versioning (mark-as-ended + new insert) instead of database-level upsert                                                                                     | `ON CONFLICT DO NOTHING` is a general best practice for idempotency in bulk inserts. However, SDEP's data model requires explicit versioning with `endedAt` timestamps. |
| **D7** | **Single transaction scope** - the entire bulk operation runs in a single transaction; if the bulk INSERT fails, all changes roll back                                                                            | No partial database state. Consistent with the single endpoint's `get_async_db` auto-commit/rollback model.                                                             |
| **D8** | **SQLite compatibility** - the bulk INSERT and all queries work on both PostgreSQL and SQLite                                                                                                                     | Unit tests run on SQLite in-memory without requiring PostgreSQL. The `StringArray` TypeDecorator handles dialect differences.                                           |
| **D9** | **Lifecycle status on activities** - activity records carry `status` with values `finished` (default) or `cancelled`; resubmitting the same `activityId` with `cancelled` creates a new current cancelled version | Allows platforms to correct previously submitted stays without changing the existing versioning model.                                                                  |

---

## Development Workflow

See makefile help
```
make
```

---

## Testing Strategy

### Unit Tests (`backend/tests/`)
- pytest with parallel execution (`-n auto`)
- Async test support
- Fixtures for database and authentication
- Code coverage tracking
- **Run:** `cd backend && make test`

### Integration Tests (`tests/`)
- Shell scripts using curl
- Test OAuth2 flows
- Test API endpoints with single-item and bulk POST payloads
- Test security headers (OWASP compliance)
- Test validation (Pydantic + business logic)
- **Run:** `make test`
- See [Integration Tests](INTEGRATION_TESTS.md) for detailed test documentation

### Performance Tests (`tests/perf/`)
- Locust-based load testing for the bulk activity endpoint (`POST /str/activities/bulk`)
- Measures throughput (activities/sec), extrapolates capacity (activities/day), compares against configurable target
- Uses isolated test data (`sdep-test-perf-*` prefix) by default; optionally keeps data in database (`PERF_KEEP_DATA=true`)
- Configurable: `PERF_ACTIVITIES_TARGET` (total target volume), `PERF_USERS` (concurrent users to reach target), `PERF_MAX_DURATION_SECONDS`, `PERF_BATCH_SIZE`, `PERF_KEEP_DATA`
- **Run:** `make test-perf` (or e.g. `make test-perf PERF_USERS=5 PERF_ACTIVITIES_TARGET=1000000 PERF_MAX_DURATION_SECONDS=10`)
- See [Performance Tests](PERFORMANCE_TESTS.md) for detailed documentation

---

## SQLite vs PostgreSQL

**Unit tests** (`backend/tests/`) automatically switch to an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) when no `DATABASE_URL` environment variable is set. This lets developers run unit tests without PostgreSQL installed or running.

**Integration tests** (`tests/`) and **Production** both use PostgreSQL (`postgresql+asyncpg`) configured via environment variables (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB_NAME`, etc.).

|                 | Production | Integration tests (`tests/`) | Unit tests (`backend/tests/`) |
| --------------- | ---------- | ---------------------------- | ----------------------------- |
| **Database**    | PostgreSQL | PostgreSQL                   | SQLite (in-memory)            |
| **Trigger**     | always     | always                       | `DATABASE_URL` not set        |
| **Persistence** | persistent | persistent                   | ephemeral (per test)          |
| **Dependency**  | `asyncpg`  | `asyncpg`                    | `aiosqlite` (dev only)        |

Because SQLite lacks some PostgreSQL features, the models include **dialect adaptors**:

- **`StringArray`** (`backend/app/models/types.py`) - uses `ARRAY(String)` on PostgreSQL and JSON-serialized `Text` on SQLite
- **`CheckConstraint`** - marked `.ddl_if(dialect="postgresql")` so they are only applied to PostgreSQL

Because some CHECK constraints rely on PostgreSQL-specific SQL (e.g. `array_length`) and cannot run on SQLite, they are declared PostgreSQL-only in both the model (`.ddl_if(dialect="postgresql")`) and the Alembic migration (wrapped in `if is_postgres:`); the DDL is skipped under SQLite, so enforcement falls back to the application layers above the DB:

- **Model** (`backend/app/models/activity.py`) - `CheckConstraint("number_of_guests = array_length(country_of_guests, 1)", name="ck_activity_guests_cardinality").ddl_if(dialect="postgresql")`
- **Migration** (`backend/alembic/versions/007_guests_required_and_cardinality.py`) - the `create_check_constraint(...)` call is inside an `if is_postgres:` guard
- **Pydantic fallback** - `ActivityRequest.validate_guest_cardinality` (`@model_validator(mode="after")`) rejects mismatched requests, covering every API/bulk path including SQLite-backed unit tests
- **Factory fallback** - `ActivityFactory.country_of_guests = LazyAttribute(lambda o: ["NLD"] * o.number_of_guests)` guarantees consistency for CRUD-level tests that call `activity.create()` directly and bypass Pydantic

A direct CRUD call on SQLite with manually mismatched lists would not be caught by either DB or Pydantic; tests must route through Pydantic or use the factory to stay consistent.

---

## Key Configuration Files

- **`.env`** - Base environment variables for local development
- **`.env.extra`** - Optional local overrides loaded by Make/docker compose when present
- **`docker-compose.yml`** - Container orchestration
- **`backend/pyproject.toml`** - Python dependencies and tool configuration
- **`backend/alembic.ini`** - Database migration configuration
- **`keycloak/machine-clients.yaml`** - Test machine client definitions (OAuth2)
- **`keycloak/roles.yaml`** - Test role definitions
- **`Makefile`** - Development automation
