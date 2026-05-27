<h1>Technical Architecture</h1>

This document provides an overview of the SDEP (Single Digital Entry Point) technical architecture.

<h2>Table of Contents</h2>

- [Overview](#overview)
- [Scope and Reference Implementation](#scope-and-reference-implementation)
- [Technology Stack](#technology-stack)
  - [Backend](#backend)
  - [Infrastructure](#infrastructure)
  - [Development Tools](#development-tools)
- [Repository / Directory Structure](#repository-directory-structure)
- [Backend Architecture](#backend-architecture)
  - [API Layer (`app/api/`)](#api-layer-appapi)
  - [Schemas Layer (`app/schemas/`)](#schemas-layer-appschemas)
  - [Service Layer (`app/services/`)](#service-layer-appservices)
  - [CRUD Layer (`app/crud/`)](#crud-layer-appcrud)
  - [Models Layer (`app/models/`)](#models-layer-appmodels)
- [API Surface](#api-surface)
  - [Authentication](#authentication)
  - [Competent Authority Endpoints](#competent-authority-endpoints)
  - [STR Platform Endpoints](#str-platform-endpoints)
  - [Health Endpoints](#health-endpoints)
  - [Request Flow](#request-flow)
- [Data and Lifecycle Design](#data-and-lifecycle-design)
  - [ID Management](#id-management)
  - [Versioning](#versioning)
  - [Deleting](#deleting)
  - [Locking](#locking)
  - [Tenant Isolation](#tenant-isolation)
  - [Lazy Loading](#lazy-loading)
  - [Data Flow](#data-flow)
- [Transaction Management](#transaction-management)
- [Validation](#validation)
  - [Layers](#layers)
  - [Functional IDs (General)](#functional-ids-general)
  - [Functional IDs (User-Supplied)](#functional-ids-user-supplied)
  - [Owner IDs and JWT Client IDs](#owner-ids-and-jwt-client-ids)
- [Status Codes and Exception Handling](#status-codes-and-exception-handling)
- [Bulk Activity Submissions](#bulk-activity-submissions)
  - [Approach](#approach)
  - [Validation Flow](#validation-flow)
  - [Status Codes](#status-codes)
  - [Design Decisions](#design-decisions)

See also: [Database Dialects](./DATABASE_DIALECTS.md) | [Development](./DEVELOPMENT.md)

---

## Overview

SDEP is a FastAPI-based REST API that enables:

- Competent Authorities (CA) to register regulated areas with geospatial data
- Short-Term Rental platforms (STR) to query regulated areas and submit rental activities
- Competent Authorities (CA) to query rental activities
- Compliance with EU Regulation 2024/1028

---

## Scope and Reference Implementation

**Production (NL):** https://sdep.gov.nl/api/docs

- This is the reference implementation for this repo

---

## Technology Stack

### Backend
- **Python:** 3.13+
- **Framework:** FastAPI 0.115+
- **ORM:** SQLAlchemy 2.0+ (async)
- **Migrations:** Alembic
- **Validation:** Pydantic 2.10+
- **Authentication:** OAuth2 Client Credentials via authorization server (e.g. Keycloak)
- **Server:** Uvicorn

### Infrastructure
- **Container Platform:** Docker + Docker Compose
- **Identity Provider:** e.g. Keycloak (OAuth2/OIDC)
- **Database:** PostgreSQL 15+
- **Package Manager:** uv (Python)

### Development Tools
- **Linting:** Ruff
- **Type Checking:** Pyright
- **Testing:** pytest (with pytest-asyncio, pytest-xdist for parallel execution)
- **Pre-commit:** Hooks for code quality
- **CI/CD:** GitLab CI or otherwise (out of scope for this project)

---

## Repository / Directory Structure

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
│   │   │   ├── common_app.py                   # Version-independent sub-app (health, ping)
│   │   │   └── domains/                        # Per-domain versioned sub-apps
│   │   │       ├── auth/
│   │   │       │   └── v1.py                   # Auth domain sub-app
│   │   │       ├── ca/
│   │   │       │   └── v1.py                   # CA domain sub-app
│   │   │       └── str/
│   │   │           └── v1.py                   # STR domain sub-app
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
│   │   │   ├── address.py
│   │   │   ├── area.py
│   │   │   ├── auth.py
│   │   │   ├── common.py                       # Shared types: FunctionalId, validate_functional_id()
│   │   │   ├── error.py
│   │   │   ├── health.py
│   │   │   └── temporal.py
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
│   │       └── 001_initial.py                  # Initial migration
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
│   ├── test_smoketest.sh                       # Smoke test audit-excluded endpoints
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
│   ├── realm.yaml                              # Realm configuration
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
│   ├── ARCHITECTURE_FUNC.md                    # Functional architecture
│   ├── ARCHITECTURE_TECH.md                    # Architecture overview (this file)
│   ├── DATABASE_DIALECTS.md                    # SQLite/PostgreSQL compatibility
│   ├── DATAMODEL.md                            # Data Model documentation
│   ├── DEVELOPMENT.md                          # Workflow, testing, configuration
│   ├── GET_STARTED_PRD.md                      # Getting started with the production (PRD) environment
│   ├── GET_STARTED_PRE.md                      # Getting started with the pre-production (PRE) environment
│   ├── INTEGRATION_TESTS.md                    # Integration test documentation
│   ├── LISTING_ACTIVITY.md                     # Activity listing documentation
│   ├── MIGRATION_ADDRESS_INSPIRE.md            # Address field migration guide (INSPIRE/STR-AP)
│   ├── PERFORMANCE_TESTS.md                    # Performance test documentation
│   ├── SECURITY.md                             # Security documentation
│   ├── WOW.md                                  # Ways of working
│   ├── sdep_openapi_auth_v1.pdf                # OpenAPI auth v1 PDF export
│   ├── sdep_openapi_ca_v1.pdf                  # OpenAPI CA v1 PDF export
│   ├── sdep_openapi_str_v1.pdf                 # OpenAPI STR v1 PDF export
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
- Does not commit or roll back transactions directly (delegated to API layer)

### CRUD Layer (`app/crud/`)
- Database operations (Create, Read, Update, Delete)
- Data access abstraction
- SQLAlchemy query construction
- Uses flush (not commit) - defers transaction control to upper layers

### Models Layer (`app/models/`)
- SQLAlchemy ORM models
- Database table definitions
- Relationships and constraints
- Includes `audit_log.py` for audit trail

For key patterns, see also [Data Model](./DATAMODEL.md), [Security](./SECURITY.md), and [API](./API.md).

---

## API Surface

### Authentication
- `POST /api/auth/v1/token` - OAuth2 token endpoint

### Competent Authority Endpoints
- `POST /api/ca/v1/areas` - Submit a single area (multipart/form-data: file + optional areaId, areaName)
- `GET /api/ca/v1/areas` - List own areas (pagination: offset, limit)
- `GET /api/ca/v1/areas/count` - Count own areas
- `GET /api/ca/v1/areas/{areaId}` - Download shapefile for own area
- `DELETE /api/ca/v1/areas/{areaId}` - Delete (deactivate) an own area
- `GET /api/ca/v1/activities` - Query rental activities (pagination: offset, limit)
- `GET /api/ca/v1/activities/count` - Count activities

### STR Platform Endpoints
- `GET /api/str/v1/areas` - List regulated areas (pagination: offset, limit)
- `GET /api/str/v1/areas/count` - Count areas
- `GET /api/str/v1/areas/{areaId}` - Download shapefile for area
- `POST /api/str/v1/activities/bulk` - Submit up to 1000 activities in bulk (JSON body)

### Health Endpoints
- `GET /api/health` - Health check (unauthenticated, infrastructure use)
- `GET /api/ping` - Ping endpoint (authenticated, requires valid bearer token)

---

### Request Flow

```
POST /api/str/v1/activities/bulk (JSON body with activities array)
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

POST /api/ca/v1/areas (multipart/form-data: file + optional areaId, areaName)
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

## Data and Lifecycle Design

### ID Management

**Technical IDs**

- Represent technical keys, on the **"inside"** (under the hood)
- These are used for referential integrity within the database

**Functional IDs**

- Represent business identifiers, on the **"outside"**
- Are client-provided (optional), or auto-provisioned otherwise (UUIDv4 RFC 9562)
  - Exception: `platformId` and `competentAuthorityId` are never client-provided; they are always auto-provisioned server-side (UUIDv4 RFC 9562). The owning identity comes from the JWT `client_id` claim, which is stored separately as `clientId`.
- After a POST, functional IDs are always returned/made visible
- This allows them to be reused in subsequent submissions
- Functional IDs enable versioning (in combination with a timestamp)

https://datatracker.ietf.org/doc/rfc9562/

### Versioning

- Same functional ID can be resubmitted with new timestamp for versioning
  - Entities use `(functionalId, createdAt)` as unique constraint
- Stacking
  - Last becomes current (empty `endedAt`)
  - Previous becomes ended (`endedAt`)
- Enables historical tracking and updates without losing previous versions
- Standard retrieve only yields the current

### Deleting

---

**Soft-Delete**

- When all versions of a functional ID have `endedAt` set, the entity is considered **deactivated**
- Creating a new version with a deactivated functional ID is rejected (HTTP 422)
- This prevents "resurrecting" soft-deleted entities
- The guard applies to: `competentAuthorityId`, `platformId`, `areaId`, and `activityId`

---

**Hard-Delete**

Hard-delete removes a row from the database (as opposed to soft-delete, which sets `endedAt`).

When a parent row has child rows referencing it via a foreign key, the database must decide what to do with those children. The three standard behaviors are:

| Behavior       | FK clause                                     | Effect                                                 | When to use                                                                                  |
| :------------- | :-------------------------------------------- | :----------------------------------------------------- | :------------------------------------------------------------------------------------------- |
| **Restricted** | `NO ACTION` / `RESTRICT` (PostgreSQL default) | Parent delete is **blocked** if children exist         | When children must not exist without their parent, and accidental deletion must be prevented |
| **Nullified**  | `ON DELETE SET NULL`                          | Child FK column is set to `NULL`; children survive     | When children can exist independently (optional relationship)                                |
| **Cascaded**   | `ON DELETE CASCADE`                           | Children are **automatically deleted** with the parent | When children have no meaning without their parent (composition)                             |

**Current implementation:**

All foreign keys use the PostgreSQL default (`NO ACTION`), which is **restricted delete**:

| Parent             | Child         | FK column                     | Hard-delete behavior                     |
| :----------------- | :------------ | :---------------------------- | :--------------------------------------- |
| CompetentAuthority | Area          | `area.competent_authority_id` | Restricted — blocked if Areas exist      |
| Area               | Activity      | `activity.area_id`            | Restricted — blocked if Activities exist |
| Platform           | Activity      | `activity.platform_id`        | Restricted — blocked if Activities exist |
| Activity           | *(leaf node)* | —                             | Unrestricted — deletes cleanly           |

In practice, the application uses **soft-delete** (`mark_as_ended`) for all operations. Hard-delete functions are not provided.

### Locking

In internet applications, three common locking strategies are typically used:

- **No locking**
  No concurrency protection is applied. This is simple and fast, but concurrent updates may overwrite each other and lead to inconsistent data.

- **Optimistic locking**
  Multiple transactions are allowed to proceed concurrently. Conflicts are detected only when data is written, typically using a version number or timestamp. If a conflict occurs, one transaction must retry.

- **Pessimistic locking**
  Data is locked before modification to prevent concurrent transactions from changing the same records simultaneously. Other transactions must wait until the lock is released.

In SDEP, **pessimistic locking** is used:

- Versioned write operations follow a *mark-as-ended → create-new-version* pattern.
- To prevent concurrent requests from creating duplicate "current" versions, these operations use `SELECT ... FOR UPDATE`.

This approach was chosen because:

- Concurrency on the same entity is expected to be very low.
- Compared to optimistic locking, pessimistic locking is simpler to implement and does not require retry logic.

Pessimistic locking applies to:

- `CompetentAuthority` versioning (single POST)
- `Area` versioning (single POST)
- `Activity` bulk versioning (bulk POST)

---

**Behavior During Concurrent Requests**

If two requests attempt to version the same entity at the same time:

1. The first request acquires the row lock
2. The second request waits until the first transaction commits
3. The second request then continues safely using the updated state

This guarantees consistent versioning without duplicate active records.

---

**Performance Considerations**

---

**Single-entity versioning**

For single-entity versioning operations, the impact of pessimistic locking is minimal.

- E.g. `POST /area`.

Lock characteristics:

- The lock is applied at **row level** (not table level)
- Only a single row is locked per transaction
- The lock is held for a very short time (~5 ms):
  - Read current version
  - Mark as ended
  - Insert new version
  - Commit transaction

Parallel processing:

- Locks are isolated per functional ID. For example:
- Locking `CompetentAuthority "0363"` does **not** block operations for other authorities
- Requests for different entities continue fully in parallel

Likelihood of contention - only occurs when:

- Two requests target the **same functional ID**, at nearly the **same moment**
- Since each Competent Authority manages only its own areas (scoped through the JWT `client_id`), this scenario is considered extremely unlikely

Expected impact:

- The expected performance impact is negligible
- The overhead of the row-level lock is significantly smaller than the database I/O cost of the query itself

**Bulk activity versioning**

Bulk versioning operations use the same locking strategy, but involve larger transactions.

- E.g. `POST /activities/bulk`

Lock characteristics:

- Locks remain **row-level**
- Up to 1000 rows may be locked in a single batch (maximum batch size)
- The transaction duration is longer because it includes:
  - Validation
  - Mark-as-ended operations
  - Bulk insert
  - Commit transaction

Typical transaction duration:

- ~50–200 ms, depending on batch size

Likelihood of contention - only occurs when:

- Two bulk requests originate from the **same platform**
- Both contain overlapping activity IDs
- Both are submitted simultaneously

Different platforms never block each other because queries are filtered by `platform_id`.

Worst-case scenario:

- The same platform submits two overlapping 1000-item batches simultaneously
- The second transaction waits for the first to complete (~200 ms)

Even in this scenario:

- No requests fail
- No data corruption occurs
- Consistency is preserved

Expected impact:

- For the expected workload (periodic batch submissions, typically one platform at a time), the performance impact is effectively unnoticeable
- The locking overhead remains lightweight compared to the database cost of the bulk insert itself

### Tenant Isolation

Each tenant — a Competent Authority (CA) for areas, or a Platform (STR) for activities — can only affect its own data. Isolation is enforced at multiple layers: JWT identity, service-layer scoping, CRUD-layer filtering, and database constraints.

---

**Area operations (CA-scoped)**

- **Create / update (versioning):** The `mark-as-ended` + `create-new-version` lookup is scoped to the authenticated CA via `get_by_area_id_and_competent_authority_id_str()` with `SELECT ... FOR UPDATE`. Another CA may hold an area with the same `areaId` — it is not affected.
- **Delete (soft-delete):** Scoped lookup by `(areaId, competentAuthorityId)`. If the area belongs to a different CA, the operation returns 404.
- **Deactivation guard:** `exists_any_by_area_id()` is CA-scoped. A deactivated `areaId` from one CA does not block another CA from using the same `areaId`.
- **DB constraint:** `UNIQUE(area_id, competent_authority_id, created_at)` allows the same `areaId` to be used independently by different CAs.

---

**Activity operations (platform-scoped)**

- **Create / update (bulk versioning):** `get_current_by_activity_ids()` and `bulk_mark_as_ended()` both filter by `platform_id`. Platform-A cannot version Platform-B's activities, even if they share the same `activityId`.
- **Delete:** No delete endpoint exists for activities.
- **DB constraint:** `UNIQUE(activity_id, platform_id, created_at)` allows the same `activityId` to be used independently by different platforms.
- **Deactivation guard:** `get_deactivated_activity_ids()` operates globally (not platform-scoped) and is called on every bulk submission. However, no code path currently puts an activity into a deactivated state — there is no DELETE endpoint, and versioning always creates a new current version. The guard is defensive: if a DELETE endpoint is added in the future, it will prevent resurrection of deactivated activities. Compare with the equivalent Area guard (`exists_any_by_area_id`), which can trigger because areas can be soft-deleted via `DELETE /ca/areas/{areaId}`.

---

**Enforcement layers**

| Layer       | Area                                                                | Activity                                                            |
| :---------- | :------------------------------------------------------------------ | :------------------------------------------------------------------ |
| **JWT**     | `client_id` identifies the CA                                       | `client_id` identifies the platform (STR)                           |
| **API**     | Passes `client.id` to service; cannot be overridden by request body | Passes `client.id` to service; cannot be overridden by request body |
| **Service** | Scoped lookups via `competent_authority_id_str`                     | Scoped lookups via `platform_id`                                    |
| **CRUD**    | WHERE clauses include `competent_authority_id`                      | WHERE clauses include `platform_id`                                 |
| **DB**      | `UNIQUE(area_id, competent_authority_id, created_at)` + FK          | `UNIQUE(activity_id, platform_id, created_at)` + FK                 |

### Lazy Loading

- **Default lazy loading**
  - Relationships have no explicit `lazy=` parameter (uses SQLAlchemy defaults)
- **Custom eager loading** via `selectinload()` at query time
  - When relationships are needed, CRUD functions explicitly load them, e.g.:
    ```python
    stmt = select(Activity).options(
        selectinload(Activity.platform),
        selectinload(Activity.area).selectinload(Area.competent_authority),
    )
    ```
- **Benefits**
  - Eager-when-needed (loads relationships in bulk via `selectinload`)
  - Idiomatic (reduced boilerplate, less-verbose than manual queries)

### Data Flow

---

**CA POST /areas**

A. Inputs:

- From JWT (verified by the auth dependency):
  - `clientId` ← `client_id` claim
  - `competentAuthorityName` ← `client_name` claim
- From multipart payload:
  - `areaId` (optional functional id, alphanumeric with hyphens, length <= 64)
  - `areaName` (optional, length <= 64)
  - `regulation` (optional enum, defaults to `all`)
  - `file` (.zip, max 1 MiB, ZIP-magic verified, malware-scanned)

B. Steps:

1. Resolve or version the `CompetentAuthority` (row-locked `FOR UPDATE` on `clientId`):

   - No row e xists for `clientId`: create a new Competent Authority
     - Technical id `id`: autogenerated (int)
     - Functional id `competentAuthorityId`: auto-generated (UUIDv4)
     - Name `competentAuthorityName`: ← JWT
     - Reference `clientId`: ← JWT
     - Timestamp `createdAt`: autogenerated (`now()`)
   - `clientId` exists and `competentAuthorityName` unchanged: reuse as is
   - `clientId` exists and `competentAuthorityName` changed: mark the current Competent Authority as ended (`endedAt = now()`) and insert a new version
     - Technical id `id`: autogenerated (int)
     - Functional id `competentAuthorityId`: same as is
     - Name `competentAuthorityName`: ← JWT
     - Reference `clientId`: same as is
     - Timestamp `createdAt`: autogenerated (`now()`)
   - Only ended rows exist for `clientId`: reject as deactivated

2. Resolve or version the `Area` (row-locked `FOR UPDATE` on `(areaId, competentAuthorityId)` when `areaId` is supplied):

   - `areaId` is not supplied: create a brand-new Area
     - Technical id `id`: autogenerated (int)
     - Functional id `areaId`: auto-generated (UUIDv4)
     - Name `areaName`: ← payload
     - Regulation `regulation`: ← payload
     - File name `filename`: ← payload
     - File data `filedata`: ← payload
     - CA reference `competent_authority_id`: ← technical `id` of the CA row from step 1
     - Timestamp `createdAt`: autogenerated (`now()`)
     - End timestamp `endedAt`: `NULL`

   - `areaId` is supplied and no row exists for `(areaId, competentAuthorityId)`: create a new Area using the supplied functional id
     - Technical id `id`: autogenerated (int)
     - Functional id `areaId`: ← payload
     - Name `areaName`: ← payload
     - Regulation `regulation`: ← payload
     - File name `filename`: ← payload
     - File data `filedata`: ← payload
     - CA reference `competent_authority_id`: ← technical `id` of the CA row from step 1
     - Timestamp `createdAt`: autogenerated (`now()`)
     - End timestamp `endedAt`: `NULL`

   - `areaId` is supplied and an active row exists for `(areaId, competentAuthorityId)`: mark the current Area as ended (`endedAt = now()`) and insert a new version
     - Technical id `id`: autogenerated (int)
     - Functional id `areaId`: same as supplied
     - Name `areaName`: ← payload
     - Regulation `regulation`: ← payload
     - File name `filename`: ← payload
     - File data `filedata`: ← payload
     - CA reference `competent_authority_id`: ← technical `id` of the CA row from step 1
     - Timestamp `createdAt`: autogenerated (`now()`)
     - End timestamp `endedAt`: `NULL`

   - `areaId` is supplied and only ended rows exist for `(areaId, competentAuthorityId)`: reject as deactivated

3. Commit at the API transaction boundary (CRUD layer only flushes)

Net effect:

- 1x new `competent_authority` row inserted only when the CA is new or its name changed; the previous version is marked ended in the latter case
- 1x new `area` row, with FK `area.competent_authority_id → competent_authority.id`
- Optionally 1 old `area` row marked ended if the same `areaId` was resubmitted for this CA

---

**STR POST /activities/bulk**

A. Inputs:

- From JWT (verified by the auth dependency):
  - `clientId` ← `client_id` claim
  - `platformName` ← `client_name` claim
- From JSON payload:
  - `activities`: array of 1–1000 activity items; each item carries:
    - `activityId` (optional functional id, alphanumeric with hyphens, length <= 64)
    - `activityName` (optional, length <= 64)
    - `status` (optional enum, defaults to `finished`; may also be `cancelled`)
    - `areaId` (required functional id, must reference an existing area)
    - `url` (length <= 128)
    - `address` (composite: `thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)
    - `registrationNumber` (length <= 32)
    - `numberOfGuests` (1–1024)
    - `countryOfGuests` (array, 1–1024 elements; each ISO 3166-1 alpha-3 or `N/A`, uppercase; length must equal `numberOfGuests`)
    - `temporal` (composite: `startDatetime`, `endDatetime`)

B. Steps:

1. Per-item Pydantic validation (`TypeAdapter(ActivityRequest)`):

   - Invalid items are marked NOK with their errors; valid items continue
   - The original client-supplied `activityId` (or `None`) is preserved for the response
   - For valid items, a missing `activityId` is auto-generated (UUIDv4)

2. Resolve or version the `Platform` once per batch:

   - No row exists for `clientId`: create a new Platform
     - Technical id `id`: autogenerated (int)
     - Functional id `platformId`: auto-generated (UUIDv4)
     - Name `platformName`: ← JWT
     - Reference `clientId`: ← JWT
     - Timestamp `createdAt`: autogenerated (`now()`)
   - `clientId` exists and `platformName` unchanged: reuse as is
   - `clientId` exists and `platformName` changed: mark the current Platform as ended (`endedAt = now()`) and insert a new version
     - Technical id `id`: autogenerated (int)
     - Functional id `platformId`: same as is
     - Name `platformName`: ← JWT
     - Reference `clientId`: same as is
     - Timestamp `createdAt`: autogenerated (`now()`)
   - Only ended rows exist for `clientId`: reject as deactivated

3. Intra-batch deduplication on `activityId` (last-wins): when a batch contains multiple valid items with the same `activityId`, only the last occurrence proceeds; earlier occurrences are marked NOK with a "superseded by later item in batch at index N" error.

4. Referential integrity check (single query): resolve `areaId` → technical `id` (and owning CA) for all referenced areas via `get_area_ca_map`. Items pointing at unknown areas are marked NOK.

5. Resolve or version each `Activity` (row-locked `FOR UPDATE` on `(activityId, platformId)` when `activityId` is supplied):

   - `activityId` was auto-generated in step 1: defer to step 6 (no versioning lookup; brand-new functional id)
   - `activityId` is supplied and no active row exists for `(activityId, platformId)`: defer to step 6 (insert using the supplied functional id)
   - `activityId` is supplied and an active row exists for `(activityId, platformId)`: mark the current Activity as ended (`endedAt = now()`); the new version is inserted in step 6
   - `activityId` is supplied and only ended rows exist (across any platform): reject as deactivated

6. Bulk insert all remaining valid items in a single multi-row INSERT, using one `batch_created_at` (= `now()` at INSERT time) for the whole batch. Each new `activity` row:

   - Technical id `id`: autogenerated (int)
   - Functional id `activityId`: ← validated request (supplied, or auto-generated UUIDv4 from step 1)
   - Functional columns from the payload (`activityName`, `status`, `url`, address fields, `registrationNumber`, `numberOfGuests`, `countryOfGuests`, temporal fields)
   - Platform reference `platform_id` (FK): ← technical `id` of the Platform row from step 2
   - Area reference `area_id` (FK): ← technical `id` resolved in step 4
   - Timestamp `createdAt`: ← `batch_created_at`
   - End timestamp `endedAt`: `NULL`

7. Commit at the API transaction boundary (CRUD layer only flushes); on any exception the whole batch rolls back.

8. Return a per-item OK/NOK response preserving the original request order. HTTP status: `201` if all items succeeded, `200` on partial success, `422` if all items failed.

Net effect:

- 1x new `platform` row inserted only when the platform is new or its name changed; the previous version is marked ended in the latter case
- N new `activity` rows (one per valid item), each with FKs `activity.platform_id → platform.id` and `activity.area_id → area.id`
- Optionally M old `activity` rows marked ended when a supplied `activityId` had an active version for this platform

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

### Functional IDs (General)

All functional IDs conform to a single pattern defined in `app/schemas/common.py`:

```
^[A-Za-z0-9-]+$    (1–64 characters, alphanumeric with hyphens)
```

This pattern is expressed as two reusable types:

| Type                   | Base type     | Used for                                                                                         |
| ---------------------- | ------------- | ------------------------------------------------------------------------------------------------ |
| `FunctionalId`         | `str`         | IDs that **must** be present (references to existing entities, response fields, path parameters) |
| `OptionalFunctionalId` | `str \| None` | IDs that **may** be omitted (create inputs where the system generates a UUID if not provided)    |


### Functional IDs (User-Supplied)

**Area and Activity functional IDs** are user-supplied.

These IDs are submitted by the caller in the request body or form fields and validated **declaratively by Pydantic** before the endpoint function body runs:

| Endpoint                           | Field                 | Type                   | Pydantic validates?                                       | When omitted                                                |
| ---------------------------------- | --------------------- | ---------------------- | --------------------------------------------------------- | ----------------------------------------------------------- |
| `POST /api/ca/v1/areas`            | `areaId` (form field) | `OptionalFunctionalId` | Yes - `Annotated[OptionalFunctionalId, Form()]`           | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |
| `POST /api/str/v1/activities/bulk` | `activityId` per item | `OptionalFunctionalId` | Yes - via `TypeAdapter(ActivityRequest)` in service layer | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |

**Why `POST /api/ca/v1/areas` uses `Form()` instead of a JSON body** (see implementation):

- `POST /api/ca/v1/areas` accepts **multipart/form-data** (required for file upload), so each field is an individual `Form()` parameter
  - The `Annotated[OptionalFunctionalId, Form()]` type annotation ensures Pydantic still validates the form field declaratively, just like JSON body fields
- `POST /api/str/v1/activities/bulk` accepts a JSON body; per-item validation is done via `TypeAdapter(ActivityRequest)` in the service layer

### Owner IDs and JWT Client IDs

**Platform and Competent Authority public functional IDs** are generated UUID strings stored in `platform.platform_id` and `competent_authority.competent_authority_id`.

These public owner IDs are returned as `platformId` and `competentAuthorityId` in API responses. They are not supplied in request payloads and are not derived from JWT usernames or client identifiers.

The JWT token's `client_id` claim is stored separately in the private `client_id` column on `Platform` and `CompetentAuthority`. Service and CRUD code use this private value for lookup, ownership scoping, versioning, and deactivation checks.

| Endpoint                           | Router                   | JWT claim used for scoping | Public owner ID exposed in responses |
| ---------------------------------- | ------------------------ | -------------------------- | ------------------------------------ |
| `POST /api/ca/v1/areas`            | `ca_areas.py`            | `client_id`                | `competentAuthorityId`               |
| `GET /api/ca/v1/areas`             | `ca_areas.py`            | `client_id`                | `competentAuthorityId`               |
| `GET /api/ca/v1/areas/count`       | `ca_areas.py`            | `client_id`                | n/a                                  |
| `GET /api/ca/v1/areas/{areaId}`    | `ca_areas.py`            | `client_id`                | n/a                                  |
| `DELETE /api/ca/v1/areas/{areaId}` | `ca_areas.py`            | `client_id`                | n/a                                  |
| `GET /api/ca/v1/activities`        | `ca_activities.py`       | `client_id`                | `competentAuthorityId`, `platformId` |
| `GET /api/ca/v1/activities/count`  | `ca_activities.py`       | `client_id`                | n/a                                  |
| `POST /api/str/v1/activities/bulk` | `str_activities_bulk.py` | `client_id`                | `competentAuthorityId`, `platformId` |

The private `client_id` is never serialized in public API responses, OpenAPI examples, or public documentation as an owner ID.

---

## Status Codes and Exception Handling

For the complete list of HTTP status codes used by the API, see [HTTP Status Codes](API.md#http-status-codes).

All exceptions are handled by global exception handlers defined in `app/exceptions/handlers.py` and registered in `app/api/common/exception_handlers.py`.

The table below shows how application exceptions map to HTTP status codes:

| HTTP Status                 | Exception                             | Description                                                                                                   |
| --------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 400                         | `RequestValidationError`              | Invalid query parameters on a GET request (e.g. `offset=-1` or `limit=abc`)                                   |
| 400 / 401 / 403 / 404 / 413 / 422 | `HTTPException`                       | Missing/invalid token claims, missing roles, missing credentials, inline input validation, resource not found, oversized upload (`Content-Length` exceeds the per-endpoint cap) |
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

## Bulk Activity Submissions

The bulk endpoint `POST /api/str/v1/activities/bulk` is the single entry point for all STR activity submissions.

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

### Validation Flow

Instead of having the database check each record via savepoints, errors are caught in the application layer:

- Application-level Pydantic validation is **many times faster** than database savepoints
- **Horizontally scalable**: add more API nodes under load
- **Single reference query per batch** (not per record)
- Only "clean" (validated) data reaches the database
- No savepoints or nested transactions needed, which avoids the overhead of extra database round-trips

The wire contract (OpenAPI) and the runtime validation behavior are deliberately decoupled:

- **Contract (OpenAPI)** — `ActivityBulkRequest.activities` is typed concretely as `list[ActivityRequest]`, so the spec documents the full item shape instead of an untyped object.
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

| Step                               | What                                                                                                                                                                                                                  | How                                                       |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **1. Pydantic Check**              | Validate each item individually against the ActivityRequest schema. Mark failed items as NOK with the error reason.                                                                                                   | `TypeAdapter(ActivityRequest).validate_python()` per item |
| **2. Referential Integrity Check** | For the remaining OK records: fetch all referenced area IDs in a single query. Store in a Python `dict` for O(1) lookup. Items with unknown `areaId` → NOK.                                                           | `SELECT area_id, id FROM area WHERE area_id IN (...)`     |
| **3. Bulk Insert**                 | For the remaining OK records: insert in a single database operation.                                                                                                                                                  | `session.execute(insert(Activity), list_of_valid_dicts)`  |
| **4. Feedback**                    | Return per-item OK/NOK response preserving original order, enriched with batch-item `status`, embedded `activity` (OK) or `errorMessages` array (NOK). The embedded activity also carries its own lifecycle `status`. | JSON response with summary counts                         |

**Motivation for step 2 after step 1:** \
Prevents unvalidated (untrusted) data from being used in database operations.

### Status Codes

| HTTP Status                   | When                                                                |
| ----------------------------- | ------------------------------------------------------------------- |
| **201 Created**               | All items created successfully (`failed == 0`)                      |
| **200 OK**                    | Partial success: some OK, some NOK (`succeeded > 0 AND failed > 0`) |
| **422 Unprocessable Content** | All items failed validation (`succeeded == 0`)                      |

### Design Decisions

| #      | Decision                                                                                                                                                                                                          | Rationale                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | **Per-item Pydantic validation** - the request accepts raw dicts, each validated individually in the service layer                                                                                                | One invalid item should not block the other (999) items in the batch. If one item has a missing field, the rest are still processed.                                                                                                                                                                                                                                                                                                    |
| **D2** | **Intra-batch duplicates: last-wins** - when the same `activityId` appears multiple times in a single batch, only the last occurrence is processed; earlier occurrences receive NOK                               | Deterministic and predictable for clients. Avoids ambiguity about which version "wins". Combined with pessimistic locking ([Locking](#locking)), this extends across requests: if two concurrent batches contain the same `activityId`, `SELECT ... FOR UPDATE` serializes them so the second batch waits for the first to commit, then overwrites it — consistent last-wins semantics at both the intra-batch and cross-request level. |
| **D3** | **Versioning: batch UPDATE before INSERT** - existing current versions in the database are marked as ended via a single batch `UPDATE ... WHERE activity_id IN (...)` before the bulk INSERT creates new versions | Consistent with single-endpoint versioning semantics, but uses batch operations (1 UPDATE + 1 INSERT) instead of per-item queries.                                                                                                                                                                                                                                                                                                      |
| **D4** | **Platform resolution: version only on name change** - platform is resolved once per batch; a new version is only created if the JWT claim (`client_name`) has changed                                            | Avoids unnecessary versioning churn when the same platform submits many batches with unchanged credentials.                                                                                                                                                                                                                                                                                                                             |
| **D5** | **Deactivated entities rejected** - if an `activityId` has been deactivated (all versions have `endedAt` set), submitting it again is rejected (NOK)                                                              | Prevents "resurrecting" soft-deleted entities. Consistent with single endpoint behavior.                                                                                                                                                                                                                                                                                                                                                |
| **D6** | **No `ON CONFLICT DO NOTHING`** - SDEP uses explicit versioning (mark-as-ended + new insert) instead of database-level upsert                                                                                     | `ON CONFLICT DO NOTHING` is a general best practice for idempotency in bulk inserts. However, SDEP's data model requires explicit versioning with `endedAt` timestamps.                                                                                                                                                                                                                                                                 |
| **D7** | **Single transaction scope** - the entire bulk operation runs in a single transaction; if the bulk INSERT fails, all changes roll back                                                                            | No partial database state. Consistent with the single endpoint's `get_async_db` auto-commit/rollback model.                                                                                                                                                                                                                                                                                                                             |
| **D8** | **SQLite compatibility** - the bulk INSERT and all queries work on both PostgreSQL and SQLite                                                                                                                     | Unit tests run on SQLite in-memory without requiring PostgreSQL. The `StringArray` TypeDecorator handles dialect differences.                                                                                                                                                                                                                                                                                                           |
| **D9** | **Lifecycle status on activities** - activity records carry `status` with values `finished` (default) or `cancelled`; resubmitting the same `activityId` with `cancelled` creates a new current cancelled version | Allows platforms to correct previously submitted stays without changing the existing versioning model.                                                                                                                                                                                                                                                                                                                                  |
