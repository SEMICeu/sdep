<h1>Architecture</h1>

This document provides an overview of the SDEP (Single Digital Entry Point) project structure, technology stack, and key components.

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
- [Transaction Management](#transaction-management)
- [Exception Handling](#exception-handling)
- [Development Workflow](#development-workflow)
- [Testing Strategy](#testing-strategy)
  - [Unit Tests (`backend/tests/`)](#unit-tests-backendtests)
  - [Integration Tests (`tests/`)](#integration-tests-tests)
- [SQLite vs PostgreSQL](#sqlite-vs-postgresql)
- [Key Configuration Files](#key-configuration-files)
- [Authentication \& Authorization](#authentication-authorization)


## Overview

SDEP is a FastAPI-based REST API that enables:

- Competent Authorities (CA) to register regulated areas with geospatial data
- Short-Term Rental platforms (STR) to query regulated areas and submit rental activities
- Competent Authorities (CA) to query rental activities
- Compliance with EU Regulation 2024/1028

**Production (NL):** https://sdep.gov.nl/api/v0/docs

- This is the reference implementation for this repo

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

## Directory Structure

```
sdep-app/
├── backend/                                # Python FastAPI application
│   ├── app/                                # Application code
│   │   ├── api/                            # API layer (routers, endpoints)
│   │   │   ├── common/                     # Shared API components
│   │   │   │   ├── routers/                # API routers
│   │   │   │   │   ├── auth.py             # Authentication router
│   │   │   │   │   ├── ca_activities.py    # CA activity endpoints
│   │   │   │   │   ├── ca_areas.py         # CA area endpoints
│   │   │   │   │   ├── health.py           # Health check router
│   │   │   │   │   ├── ping.py             # Ping endpoint
│   │   │   │   │   ├── str_activities.py   # STR activity endpoints
│   │   │   │   │   └── str_areas.py        # STR area endpoints
│   │   │   │   ├── exception_handlers.py
│   │   │   │   ├── openapi.py
│   │   │   │   └── security.py
│   │   │   └── v0/                         # API version 0
│   │   │       ├── main.py                 # API v0 entry point
│   │   │       └── security.py             # v0 security configuration
│   │   ├── crud/                           # Database operations (CRUD)
│   │   │   ├── activity.py
│   │   │   ├── area.py
│   │   │   ├── competent_authority.py
│   │   │   └── platform.py
│   │   ├── db/                             # Database configuration
│   │   │   └── config.py                   # Database session management
│   │   ├── exceptions/                     # Custom exceptions
│   │   │   ├── auth.py                     # Authentication exceptions
│   │   │   ├── base.py                     # Base exception classes
│   │   │   ├── business.py                 # Business logic exceptions
│   │   │   ├── handlers.py                 # Exception handlers
│   │   │   └── validation.py               # Validation exceptions
│   │   ├── models/                         # SQLAlchemy ORM models
│   │   │   ├── activity.py
│   │   │   ├── address.py
│   │   │   ├── area.py
│   │   │   ├── competent_authority.py
│   │   │   ├── platform.py
│   │   │   └── temporal.py
│   │   ├── schemas/                        # Pydantic schemas (request/response)
│   │   │   ├── activity.py
│   │   │   ├── area.py
│   │   │   ├── auth.py
│   │   │   ├── error.py
│   │   │   ├── health.py
│   │   │   └── validation.py
│   │   ├── security/                       # Security utilities
│   │   │   ├── bearer.py                   # Bearer token handling
│   │   │   └── headers.py                  # Security headers
│   │   ├── services/                       # Business logic layer
│   │   │   ├── activity.py
│   │   │   └── area.py
│   │   ├── config.py                       # Application configuration
│   │   └── main.py                         # Application entry point
│   ├── alembic/                            # Database migrations
│   │   ├── env.py                          # Alembic environment config
│   │   └── versions/                       # Migration scripts
│   │       └── 001_initial.py              # Initial migration
│   ├── tests/                              # Unit tests (mirrors app/ structure)
│   │   ├── api/                            # API layer tests
│   │   ├── crud/                           # CRUD layer tests
│   │   ├── fixtures/                       # Test fixtures and factories
│   │   ├── security/                       # Security tests
│   │   ├── services/                       # Service layer tests
│   │   └── conftest.py                     # pytest configuration
│   ├── alembic.ini                         # Alembic configuration
│   ├── Dockerfile                          # Backend container image
│   ├── Makefile                            # Backend-specific make targets
│   ├── pyproject.toml                      # Python project configuration (uv)
│   └── uv.lock                             # Locked dependencies
│
├── tests/                                  # Integration tests (shell scripts)
│   ├── lib/                                # Test library utilities
│   │   └── create_fixture_areas.sh         # Area fixture creation
│   ├── test_auth_client.sh                 # OAuth2 token acquisition utility
│   ├── test_auth_credentials.sh            # Test client credentials flow
│   ├── test_auth_headers.sh                # Security headers compliance
│   ├── test_auth_unauthorized.sh           # Test unauthorized access rejection
│   ├── test_ca_activities.sh               # Test CA activity endpoints
│   ├── test_ca_areas.sh                    # Test CA area submission
│   ├── test_health_ping.sh                 # Health check tests
│   ├── test_str_activities.sh              # Test STR activity submission
│   ├── test_str_areas.sh                   # Test STR area query endpoints
│   └── README.md                           # Test documentation
│
├── keycloak/                               # Keycloak configuration
│   ├── add-realm-admin.sh                  # Create realm admin user
│   ├── add-realm-machine-clients.sh        # Configure OAuth2 machine clients
│   ├── add-realm-roles.sh                  # Configure roles
│   ├── add-realm.sh                        # Initialize realm
│   ├── get-client-secret.sh                # Retrieve client secret
│   ├── machine-clients.yaml                # Machine client definitions (CA, STR)
│   ├── roles.yaml                          # Role definitions
│   └── wait.sh                             # Wait for Keycloak startup
│
├── postgres/                               # PostgreSQL initialization
│   ├── clean-app.sql                       # Database cleanup
│   ├── clean-testrun.sql                   # Test run cleanup
│   ├── count-app.sql                       # Row count queries
│   ├── init-keycloak.sql                   # Keycloak database setup
│   └── init-app.sql                        # SDEP database setup
│
├── test-data/                              # Test data for integration tests
│   ├── shapefiles/                         # Shapefile test data (zipped)
│   ├── 01-competent-authority.sql          # Competent authority fixtures
│   ├── 02-area-generated.sql               # Generated area data
│   └── generate-area-sql.sh                # Area data generator script
│
├── docs/                                   # Documentation
│   ├── APPROACH.md                         # Development approach
│   ├── ARCHITECTURE.md                     # Architecture overview (this file)
│   ├── DATAMODEL.md                        # Data model documentation
│   ├── DATAMODEL.drawio                    # Data model diagram (draw.io)
│   ├── DATAMODEL.svg                       # Data model diagram (SVG)
│   └── DESIGN.md                           # Design decisions log
│
├── .env                                    # Environment variables
├── .gitignore                              # Git ignore rules
├── .gitlab-ci.yml                          # GitLab CI/CD configuration
├── AGENTS.md                               # Claude agent configuration
├── CLAUDE.md                               # Claude Code instructions
├── docker-compose.yml                      # Multi-container orchestration
├── LICENSE.md                              # EUPL License
├── Makefile                                # Root-level make targets
└── README.md                               # Quick start guide
```

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
- camelCase aliases for JSON API (e.g. `activityId`, `areaId`, `postalCode`)
- Validation (Layer 1: type/format validation)

### Service Layer (`app/services/`)
- Business logic implementation
- Validation (Layer 2: business rules, e.g. area exists, platform lookup/creation)
- Raises `BusinessLogicError` for domain-level errors (e.g. area not found)
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

## Request Flow

```
POST /str/activities (single JSON body)
  │
  ├── API Layer (str_activities.py)
  │   ├── verify_bearer_token() → auth checks (roles, claims)
  │   ├── ActivityRequest (Pydantic) → syntax validation
  │   ├── activity.to_service_dict(platform_id, platform_name)
  │   └── get_async_db → auto-commit/rollback transaction
  │
  ├── Service Layer (activity.py)
  │   ├── create_activity(session, activity_data)
  │   ├── Validate area exists → BusinessLogicError if not
  │   ├── Lookup/create platform from JWT claims
  │   └── Create activity via CRUD
  │
  ├── CRUD Layer (activity.py)
  │   └── flush (not commit)
  │
  └── Response: 201 + ActivityResponse (camelCase JSON)

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

## Key Endpoints

### Authentication
- `POST /api/v0/auth/token` - OAuth2 token endpoint

### Competent Authority (CA) - Requires `sdep_ca` role
- `POST /api/v0/ca/areas` - Submit a single area (multipart/form-data: file + optional areaId, areaName)
- `GET /api/v0/ca/areas` - List own areas (pagination: offset, limit)
- `GET /api/v0/ca/areas/count` - Count own areas
- `DELETE /api/v0/ca/areas/{areaId}` - Delete (soft-delete) an own area
- `GET /api/v0/ca/activities` - Query rental activities (pagination: offset, limit)
- `GET /api/v0/ca/activities/count` - Count activities

### Short-Term Rental Platform (STR) - Requires `sdep_str` role
- `GET /api/v0/str/areas` - List regulated areas (pagination: offset, limit)
- `GET /api/v0/str/areas/count` - Count areas
- `GET /api/v0/str/areas/{areaId}` - Download shapefile for area
- `POST /api/v0/str/activities` - Submit a single activity (JSON body)
- `GET /api/v0/str/activities` - List own activities (pagination: offset, limit)
- `GET /api/v0/str/activities/count` - Count own activities

### Health
- `GET /api/health` - Health check (unauthenticated)
- `GET /api/v0/ping` - Ping endpoint (authenticated)

## Transaction Management

Two session factories handle different operation types:

| Dependency               | Session Type                | Transaction                                   | Used by        |
| ------------------------ | --------------------------- | --------------------------------------------- | -------------- |
| `get_async_db`           | Write (autoflush=True)      | Auto-commit on success, rollback on exception | POST endpoints |
| `get_async_db_read_only` | Read-only (autoflush=False) | No transaction overhead                       | GET endpoints  |

POST endpoints use `get_async_db` which wraps the entire request in a single transaction. If any error occurs, the entire operation is rolled back. On success, the transaction is committed automatically.

## Exception Handling

All exceptions are handled by global exception handlers registered in `app/exceptions/handlers.py`:

| Exception                | HTTP Status            | Description                                    |
| ------------------------ | ---------------------- | ---------------------------------------------- |
| `RequestValidationError` | 400 (GET) / 422 (POST) | Pydantic validation errors                     |
| `AppValidationError`     | 422                    | Custom application validation errors           |
| `BusinessLogicError`     | 422                    | Business rule violations (e.g. area not found) |
| `DuplicateResourceError` | 409                    | Duplicate resource conflict                    |
| `AuthenticationError`    | 401                    | Invalid or expired token                       |
| `AuthorizationError`     | 403                    | Insufficient permissions                       |
| `ResourceNotFoundError`  | 404                    | Resource not found                             |
| `HTTPException`          | varies                 | Generic HTTP errors                            |
| `Exception`              | 500                    | Catch-all (no stack trace exposed)             |

## Development Workflow

See makefile help
```
make
```

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
- Test API endpoints with single-item POST payloads
- Test security headers (OWASP compliance)
- Test validation (Pydantic + business logic)
- **Run:** `make test`
- See [tests/README.md](../tests/README.md) for detailed test documentation

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

- **`StringArray`** (`backend/app/models/activity.py`) — uses `ARRAY(String)` on PostgreSQL and JSON-serialized `Text` on SQLite
- **`CheckConstraint`** — marked `.ddl_if(dialect="postgresql")` so they are only applied to PostgreSQL

## Key Configuration Files

- **`.env`** - Environment variables (database, keycloak, backend config)
- **`docker-compose.yml`** - Container orchestration
- **`backend/pyproject.toml`** - Python dependencies and tool configuration
- **`backend/alembic.ini`** - Database migration configuration
- **`keycloak/machine-clients.yaml`** - Test machine client definitions (OAuth2)
- **`keycloak/roles.yaml`** - Test role definitions
- **`Makefile`** - Development automation

## Authentication & Authorization

- **Protocol:** OAuth2 Client Credentials flow
- **Identity Provider:** Keycloak
- **Token Type:** JWT Bearer tokens
- **Roles:**
  - `sdep_ca` - Competent Authority access
  - `sdep_str` - STR Platform access
  - `sdep_read` - Read operations
  - `sdep_write` - Write operations
- **JWT Claims used:**
  - `client_id` - Maps to platform/competent authority functional ID
  - `client_name` - Maps to platform/competent authority name
  - `realm_access.roles` - Role-based authorization
