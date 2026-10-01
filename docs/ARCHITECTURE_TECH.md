<h1>Technical architecture</h1>

This document provides an overview of the SDEP (Single Digital Entry Point) technical architecture.

<h2>Table of contents</h2>

- [Overview](#overview)
- [Technology stack](#technology-stack)
  - [Backend](#backend)
  - [Infrastructure](#infrastructure)
  - [Development tools](#development-tools)
- [Repository and directory structure](#repository-and-directory-structure)
- [API (versioning)](#api-versioning)
- [Application (versioning)](#application-versioning)
- [Backend](#backend-1)
  - [API layer (`app/api/`)](#api-layer-appapi)
  - [Schemas layer (`app/schemas/`)](#schemas-layer-appschemas)
  - [Service layer (`app/services/`)](#service-layer-appservices)
  - [CRUD layer (`app/crud/`)](#crud-layer-appcrud)
  - [Models layer (`app/models/`)](#models-layer-appmodels)
  - [Request flow](#request-flow)
- [Data](#data)
  - [ID management](#id-management)
  - [Versioning](#versioning)
  - [Deleting](#deleting)
  - [Locking](#locking)
  - [Tenant isolation](#tenant-isolation)
  - [Lazy loading](#lazy-loading)
  - [Data flow](#data-flow)
- [Transactions](#transactions)
- [Validations](#validations)
  - [Layers](#layers)
  - [Functional IDs (general)](#functional-ids-general)
  - [Functional IDs (user-supplied)](#functional-ids-user-supplied)
  - [Owner IDs and JWT client IDs](#owner-ids-and-jwt-client-ids)
- [Exceptions](#exceptions)
- [Bulk](#bulk)
  - [Approach](#approach)
  - [Validation flow](#validation-flow)
  - [Status codes](#status-codes)
  - [Design decisions](#design-decisions)

## Overview

SDEP is a FastAPI-based REST API that enables:

- Competent Authorities (CA) to register regulated areas with geospatial data
- Short-Term Rental platforms (STR) to query regulated areas, submit listings (random checks) and submit rental activities
- The listing screening authority (LSA) to retrieve submitted listings and return screening results (flags)
- Short-Term Rental platforms (STR) to retrieve their flagged listings and acknowledge them
- Competent Authorities (CA) to query acknowledged listings in their own areas, and rental activities
- The monitoring authorities (LMA, AMA) to query all listings and all activities
- The statistics authority (STA) to query all registered listings and rental activities for statistical analysis
- Compliance with EU Regulation 2024/1028

SDEP-NL production is the reference implementation for this repo:

https://sdep.gov.nl/api/docs.

## Technology stack

### Backend

- **Python:** 3.14+
- **Framework:** FastAPI 0.115+
- **ORM:** SQLAlchemy 2.0+ (async)
- **Migrations:** Alembic
- **Validation:** Pydantic 2.10+
- **Authentication:** OAuth 2.0 Client Credentials via authorization server (e.g. Keycloak)
- **Server:** Uvicorn

---

### Infrastructure

- **Container Platform:** Docker + Docker Compose
- **Identity Provider:** e.g. Keycloak (OAuth 2.0)
- **Database:** PostgreSQL 15+
- **Package Manager:** uv (Python)

---

### Development tools

- **Linting:** Ruff
- **Type Checking:** Pyright
- **Testing:** pytest (with pytest-asyncio, pytest-xdist for parallel execution)
- **Pre-commit:** Hooks for code quality
- **CI/CD:** Pipeline platform of choice (out of scope for this project)

## Repository and directory structure

```
sdep-app/
├── backend/                                                     # Python FastAPI application
│   ├── app/                                                     # Application code
│   │   ├── api/                                                 # API layer (routers, endpoints)
│   │   │   ├── app_factory.py                                   # Domain sub-app factory (shared setup for all domains)
│   │   │   ├── common/                                          # Shared API components (routers, openapi, security)
│   │   │   │   ├── routers/                                     # API routers
│   │   │   │   │   ├── auth.py                                  # Authentication router
│   │   │   │   │   ├── health.py                                # Health check router
│   │   │   │   │   └── ping.py                                  # Ping endpoint
│   │   │   │   ├── activity_examples.py                         # Shared OpenAPI activity response examples
│   │   │   │   ├── activity_handlers.py                         # Shared activity logic (CA v1/v2, STA and AMA)
│   │   │   │   ├── area_download.py                             # Shared area shapefile download response
│   │   │   │   ├── area_examples.py                             # Shared OpenAPI text and examples for the all-areas list
│   │   │   │   ├── auth_dependencies.py                         # Shared auth/role dependencies
│   │   │   │   ├── bulk_json.py                                 # HTTP status mapping of every bulk result
│   │   │   │   ├── exception_handlers.py
│   │   │   │   ├── filename.py                                  # Download filename sanitization
│   │   │   │   ├── listing_examples.py                          # Shared OpenAPI listing examples and field text
│   │   │   │   ├── listing_filters.py                           # Shared listing query-parameter types
│   │   │   │   ├── listing_handlers.py                          # Shared listing logic (one read, fixed scope per audience)
│   │   │   │   ├── openapi.py
│   │   │   │   ├── pagination.py                                # Shared pagination helpers
│   │   │   │   ├── reference_examples.py                        # Shared OpenAPI text for platforms and competent authorities
│   │   │   │   ├── reference_routers.py                         # Read-only platforms, competent authorities and areas routers
│   │   │   │   └── security.py
│   │   │   ├── common_app.py                                    # Version-independent sub-app (health, ping)
│   │   │   ├── domain_registry.py                               # Centralized API domain metadata (label, paths, status)
│   │   │   └── domains/                                         # Per-domain versioned sub-apps
│   │   │       ├── ama/
│   │   │       │   ├── v1.py                                    # AMA domain sub-app
│   │   │       │   └── routers/
│   │   │       │       └── activities_v1.py                     # AMA activity endpoints (read-only, as STA)
│   │   │       ├── auth/
│   │   │       │   └── v1.py                                    # Auth domain sub-app
│   │   │       ├── ca/
│   │   │       │   ├── v1.py                                    # CA domain sub-app v1
│   │   │       │   ├── v2.py                                    # CA domain sub-app v2 (with listings)
│   │   │       │   └── routers/
│   │   │       │       ├── activities_filters.py                # Shared query filters for the CA activity list and count (v1, v2)
│   │   │       │       ├── activities_v1.py                     # CA activity endpoints v1 (frozen response schemas, limit default 1000)
│   │   │       │       ├── activities_v2.py                     # CA activity endpoints v2 (limit default 1000)
│   │   │       │       ├── areas.py                             # CA area endpoints shared by every version (post, count, get, delete)
│   │   │       │       ├── areas_docs.py                        # Shared OpenAPI text and examples for the areas list
│   │   │       │       ├── areas_list_v1.py                     # CA areas list v1 (limit default 1000)
│   │   │       │       ├── areas_list_v2.py                     # CA areas list v2 (limit default 1000)
│   │   │       │       └── listings_v2.py                       # CA listing endpoints v2 (acknowledged, own areas)
│   │   │       ├── lma/
│   │   │       │   ├── v2.py                                    # LMA domain sub-app
│   │   │       │   └── routers/
│   │   │       │       └── listings_v2.py                       # LMA listing endpoints (read-only, every status)
│   │   │       ├── lsa/
│   │   │       │   ├── v2.py                                    # LSA domain sub-app
│   │   │       │   └── routers/
│   │   │       │       ├── listing_screenings_bulk_v2.py        # LSA bulk screening results endpoint
│   │   │       │       ├── listings_docs.py                     # OpenAPI text and examples for the LSA endpoints
│   │   │       │       └── listings_v2.py                       # LSA listing endpoints (pending)
│   │   │       ├── sta/
│   │   │       │   ├── v1.py                                    # STA domain sub-app v1 (activities)
│   │   │       │   ├── v2.py                                    # STA domain sub-app v2 (activities, listings)
│   │   │       │   └── routers/
│   │   │       │       ├── activities_v1.py                     # STA activity endpoints (read-only, v1 and v2)
│   │   │       │       └── listings_v2.py                       # STA listing endpoints (read-only, every status)
│   │   │       └── str/
│   │   │           ├── v1.py                                    # STR domain sub-app v1
│   │   │           ├── v2.py                                    # STR domain sub-app v2 (with listings)
│   │   │           └── routers/
│   │   │               ├── activities_bulk_docs.py              # Shared OpenAPI text and examples for the bulk endpoint
│   │   │               ├── activities_bulk_v1.py                # STR bulk activity endpoint v1
│   │   │               ├── activities_bulk_v2.py                # STR bulk activity endpoint v2 (UTC-only, regulation check)
│   │   │               ├── areas.py                             # STR area endpoints shared by every version (count, get)
│   │   │               ├── areas_list_v1.py                     # STR areas list v1 (unlimited by default)
│   │   │               ├── areas_list_v2.py                     # STR areas list v2 (limit default 1000)
│   │   │               ├── listing_acknowledgements_bulk_v2.py  # STR bulk listing acknowledgements endpoint v2
│   │   │               ├── listings_bulk_v2.py                  # STR bulk listings endpoint v2 (random checks)
│   │   │               ├── listings_docs.py                     # OpenAPI text and examples for the STR listing endpoints
│   │   │               └── listings_v2.py                       # STR listing endpoints v2 (own flagged listings)
│   │   ├── crud/                                                # Database operations (CRUD)
│   │   │   ├── activity.py
│   │   │   ├── area.py
│   │   │   ├── competent_authority.py
│   │   │   ├── listing.py
│   │   │   └── platform.py
│   │   ├── db/                                                  # Database configuration
│   │   │   └── config.py                                        # Database session management
│   │   ├── exceptions/                                          # Custom exceptions
│   │   │   ├── auth.py                                          # Authentication exceptions
│   │   │   ├── base.py                                          # Base exception classes
│   │   │   ├── business.py                                      # Business logic exceptions
│   │   │   ├── handlers.py                                      # Exception handlers
│   │   │   ├── infrastructure.py                                # Infrastructure exceptions (DB, auth server)
│   │   │   └── validation.py                                    # Validation exceptions
│   │   ├── models/                                              # SQLAlchemy ORM models
│   │   │   ├── activity.py
│   │   │   ├── address.py
│   │   │   ├── area.py
│   │   │   ├── audit_log.py                                     # Audit log record
│   │   │   ├── competent_authority.py
│   │   │   ├── listing.py
│   │   │   ├── platform.py
│   │   │   ├── temporal.py
│   │   │   └── types.py                                         # Dialect-aware TypeDecorators (e.g. StringArray)
│   │   ├── schemas/                                             # Pydantic schemas (request/response)
│   │   │   ├── activity.py
│   │   │   ├── activity_bulk.py
│   │   │   ├── activity_v1.py                                   # Frozen STR v1 bulk and CA v1 response schemas (deleted with v1)
│   │   │   ├── address.py
│   │   │   ├── area.py
│   │   │   ├── auth.py
│   │   │   ├── common.py                                        # Shared types: FunctionalId, UtcDateTime, validate_client_id()
│   │   │   ├── competent_authority.py
│   │   │   ├── error.py
│   │   │   ├── health.py
│   │   │   ├── listing.py
│   │   │   ├── listing_bulk.py
│   │   │   ├── platform.py
│   │   │   └── temporal.py
│   │   ├── security/                                            # Security utilities
│   │   │   ├── audit.py                                         # Audit logging middleware
│   │   │   ├── audit_retention.py                               # Background audit log cleanup
│   │   │   ├── headers.py                                       # Security headers
│   │   │   ├── malware_scan.py                                  # ClamAV malware scanning
│   │   │   └── upload_size.py                                   # Upload size limit, before the body is parsed
│   │   ├── services/                                            # Business logic layer
│   │   │   ├── activity.py
│   │   │   ├── activity_bulk.py
│   │   │   ├── area.py
│   │   │   ├── competent_authority.py                           # Competent authority reads
│   │   │   ├── listing.py
│   │   │   ├── listing_acknowledgement_bulk.py
│   │   │   ├── listing_bulk.py
│   │   │   ├── listing_bulk_common.py                           # Shared steps of the three listing bulk services
│   │   │   ├── listing_screening_bulk.py
│   │   │   └── platform.py                                      # Platform resolution for STR writes, platform reads
│   │   ├── config.py                                            # Application configuration
│   │   ├── enums.py                                             # Shared enumerations (Regulation, ListingStatus, ListingFlag, ActivityStatus)
│   │   └── main.py                                              # Application entry point
│   ├── alembic/                                                 # Database migrations
│   │   ├── env.py                                               # Alembic environment config
│   │   ├── script.py.mako                                       # Template for new migration scripts
│   │   └── versions/                                            # Migration scripts
│   │       ├── 001_initial.py                                   # Initial migration
│   │       └── *.py                                             # Additional migrations on top
│   ├── scripts/                                                 # Backend helper scripts
│   │   ├── check_db_matches_models.py                           # CHECK constraints and partial indexes match the models (make test-migrations)
│   │   └── wait_for_postgres.py                                 # Block until the database accepts connections
│   ├── tests/                                                   # Unit tests (mirrors app/ structure)
│   │   ├── api/                                                 # API layer tests
│   │   ├── crud/                                                # CRUD layer tests
│   │   ├── fixtures/                                            # Test fixtures and factories
│   │   ├── security/                                            # Security tests
│   │   ├── services/                                            # Service layer tests
│   │   ├── conftest.py                                          # pytest configuration
│   │   ├── test_app_misc.py                                     # Root app, lifespan and landing page
│   │   ├── test_exception_handlers.py                           # Exception handler mapping
│   │   ├── test_failure_message_summary.py                      # Terminal failure summary hook
│   │   ├── test_filename.py                                     # Download filename sanitization
│   │   ├── test_low_level_helpers.py                            # Small helpers across layers
│   │   ├── test_models_and_schemas.py                           # Model constraints and schema serializers
│   │   └── test_openapi_and_security_utils.py                   # OpenAPI post-processing and security utilities
│   ├── alembic.ini                                              # Alembic configuration
│   ├── Dockerfile                                               # Backend container image
│   ├── Makefile                                                 # Backend-specific make targets
│   ├── pyproject.toml                                           # Python project configuration (uv)
│   └── uv.lock                                                  # Locked dependencies
│
├── tests/                                                       # Integration tests + performance tests
│   ├── lib/                                                     # Test library utilities
│   │   └── create_fixture_areas.py                              # Area fixture creation
│   ├── malware/                                                 # Malware scanning tests
│   │   └── test_malware_scan.py                                 # ClamAV malware scan test
│   ├── performance/                                             # Performance tests (Locust)
│   │   └── locustfile.py                                        # Bulk activity load test
│   ├── suites.txt                                               # Integration test runs per suite, client, API version and environment
│   ├── test_auth_client_bootstrap.py                            # Bearer token acquisition utility (client secret)
│   ├── test_auth_client_jwt.py                                  # Test client-signed JWT (private_key_jwt) + roles
│   ├── test_auth_client_secret.py                               # Test client-secret authentication
│   ├── test_auth_headers.py                                     # Security headers compliance
│   ├── test_auth_unauthorized.py                                # Test unauthorized access rejection
│   ├── test_ama_activities.py                                   # Test AMA activity endpoints
│   ├── test_ca_activities.py                                    # Test CA activity endpoints
│   ├── test_ca_listings.py                                      # Test CA listing endpoints
│   ├── test_ca_areas.py                                         # Test CA area submission
│   ├── test_client_id_regex.py                                  # Test client ID regex validation
│   ├── test_cve_ids.py                                          # Guard against corrupted (year-rewritten) CVE ids
│   ├── test_health_ping.py                                      # Health check tests
│   ├── test_postgres_check_constraints.py                       # Test database check constraints
│   ├── test_reference_data.py                                   # Test platforms, competent authorities and areas reads
│   ├── test_lma_listings.py                                     # Test LMA listing endpoints
│   ├── test_lsa_listings.py                                     # Test LSA endpoints and the listing lifecycle
│   ├── test_sta_activities.py                                   # Test STA activity endpoints
│   ├── test_sta_listings.py                                     # Test STA listing endpoints
│   ├── test_smoketest.py                                        # Smoke test audit-excluded endpoints
│   ├── test_str_activities.py                                   # Test STR activity submission (bulk endpoint)
│   ├── test_str_listings.py                                     # Test STR listing endpoints
│   ├── test_str_areas.py                                        # Test STR area query endpoints
│   ├── test_suites.py                                           # Check that tests/suites.txt lists every test (make test-suites)
│   └── test_trivy_allowlist.py                                  # Test CVE allowlist policy validation
│
├── keycloak/                                                    # Keycloak config
│   ├── Dockerfile                                               # Optimized image (build-time options baked in)
│   ├── add-realm-admin.sh                                       # Create realm admin user
│   ├── add-realm-machine-clients.sh                             # Configure OAuth 2.0 machine clients
│   ├── add-realm-roles.sh                                       # Configure roles
│   ├── add-realm.sh                                             # Initialize realm
│   ├── get-client-secret.sh                                     # Retrieve client secret
│   ├── machine-clients.yaml                                     # Machine client definitions (CA, STR, STA, LSA, LMA, AMA)
│   ├── realm.yaml                                               # Realm configuration
│   ├── roles.yaml                                               # Role definitions
│   └── wait.sh                                                  # Wait for Keycloak startup
│
├── postgres/                                                    # PostgreSQL initialization
│   ├── clean-app.sql                                            # Database cleanup
│   ├── clean-testrun.sql                                        # Test run cleanup
│   ├── count-app.sql                                            # Row count queries
│   ├── init-keycloak.sql                                        # Keycloak database setup
│   └── init-app.sql                                             # SDEP database setup
│
├── test-data/                                                   # Test data for integration tests
│   ├── shapefiles/                                              # Shapefile test data (zipped)
│   ├── 01-competent-authority.sql                               # Competent authority fixtures
│   ├── 02-area-generated.sql                                    # Generated area data
│   └── postgres-prep-area-sql.sh                                # Area data generator script
│
├── docs/                                                        # Documentation
│   ├── ACTIVITY_FUNC.md                                         # Activity functional design
│   ├── ACTIVITY_TECH.md                                         # Activity technical design
│   ├── API_TECH.md                                              # API technical design
│   ├── API_DIFF_TECH.md                                         # Generated diff between consecutive API versions
│   ├── ARCHITECTURE_FUNC.md                                     # Functional architecture
│   ├── ARCHITECTURE_TECH.md                                     # Architecture overview (this file)
│   ├── AREA_FUNC.md                                             # Area functional design
│   ├── AREA_TECH.md                                             # Area technical design
│   ├── DATABASE_DIALECTS.md                                     # SQLite/PostgreSQL compatibility
│   ├── DATAMODEL_TECH.md                                        # Internal data model technical design
│   ├── DEFINITIONS.md                                           # Informal definitions of SDEP concepts
│   ├── DEVELOPMENT.md                                           # Workflow, testing, configuration
│   ├── GET_STARTED_CLIENT_SIGNED_JWT.md                         # Getting started with client-signed JWT (private_key_jwt)
│   ├── GET_STARTED_PRD.md                                       # Getting started with the production (PRD) environment
│   ├── GET_STARTED_PRE.md                                       # Getting started with the pre-production (PRE) environment
│   ├── HOST_FUNC.md                                             # Host role (out of scope for SDEP)
│   ├── HOST_TECH.md                                             # Host technical design (not applicable, out of scope)
│   ├── INTEGRATION_TESTS.md                                     # Integration test documentation
│   ├── LISTING_FUNC.md                                          # Listing functional design
│   ├── LISTING_TECH.md                                          # Listing technical design
│   ├── MIGRATION_ADDRESS_INSPIRE.md                             # Address field migration guide (INSPIRE/STR-AP)
│   ├── PERFORMANCE_TESTS.md                                     # Performance test documentation
│   ├── SECURITY.md                                              # Security documentation
│   ├── STR Regulation QA rev.pdf                                # Q&A on STR Regulation random checks (Article 7)
│   ├── WOW.md                                                   # Ways of working
│   ├── sdep_openapi_auth_v1.pdf                                 # OpenAPI auth v1 PDF export
│   ├── sdep_openapi_ca_v1.pdf                                   # OpenAPI CA v1 PDF export
│   ├── sdep_openapi_str_v1.pdf                                  # OpenAPI STR v1 PDF export
│   ├── diagrams/                                                # Architecture diagrams
│   │   └── ARCHITECTURE_FUNC.png
│   └── markdown-tooling/                                        # Markdown format/lint tooling (see `make md-format`, `make md-lint`)
│       ├── markdownlint-rules/                                  # Custom markdownlint rules
│       └── mdformat/                                            # mdformat plugin enforcing the project style rules
│
├── scripts/                                                     # Utility scripts
│   ├── api-versions.sh                                          # Print the API versions of a test (tests/suites.txt)
│   ├── check_architecture_tree.py                               # Check this directory tree against the filesystem (make dod)
│   ├── check_changelog.sh                                       # Changelog currency against the git log (make dod)
│   ├── check_cve_allowlist.py                                   # Reconcile Trivy report vs CVE_EXPLAINS.md (own allowlist, not published)
│   ├── check_dead_links.py                                      # Check Markdown links and anchors (make dod)
│   ├── check_docs_consistency.py                                # Routes, columns, roles, domain names and test scripts against the docs (make dod)
│   ├── check_forbidden_references.sh                            # Public-tree gate: no private paths, deployment repo or issue numbers named (make dod, mirror sync)
│   ├── create-client-signed-jwt.py                              # Create a client-signed JWT assertion (portable, standalone)
│   ├── generate-eicar-zip.sh                                    # Generate EICAR test archive (malware scan test)
│   ├── generate-keycloak-machine-clients.py                     # Generate client-signed JWT test clients (CA, STR, STA, LSA, LMA, AMA)
│   ├── public_files.sh                                          # List the public files (git-known minus export-ignore), used by the gates and Markdown targets
│   ├── run-dod.sh                                               # Definition of Done runner (make dod)
│   ├── run-suite.sh                                             # Run one suite of tests/suites.txt locally (make test-<suite>)
│   ├── run-tests.sh                                             # Integration test runner
│   ├── run-tests-perf.sh                                        # Performance test runner (Locust)
│   ├── run-trivy-scan.sh                                        # Run Trivy and emit the JSON report (scan only)
│   ├── show-keycloak-client-jwks.py                             # Show a client's public key (JWKS) stored in Keycloak
│   ├── suites.sh                                                # Print the test runs of one environment (tests/suites.txt)
│   └── validate-client-key-pair.py                              # Verify a private key matches the configured public key
│
├── .codespellrc                                                 # Spell check config: typos and Oxford spelling (see `make spell-check`)
├── .env                                                         # Environment variables
├── .env.extra.example                                           # Template for `.env.extra`, the optional local override file
├── .gitignore                                                   # Git ignore rules
├── CHANGELOG.md                                                 # Changelog
├── docker-compose.yml                                           # Multi-container orchestration
├── LICENSE.md                                                   # EUPL License
├── Makefile                                                     # Root-level make targets
└── README.md                                                    # Quick start guide
```

## API (versioning)

See separate [API design document](API_TECH.md).

## Application (versioning)

Backward compatibility:

- Clients that are built against an older contract, continue to work against a newer release of the same API version
- This is the primary design goal: existing integrations must not break on a same-version update

Forward compatibility:

- An older server gracefully handling newer client payloads (e.g. by ignoring unknown fields)
- Is a best-effort courtesy, not a guarantee across API versions

The deployed application (serving the contract) follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):

- **MAJOR** - incompatible changes (e.g. architectural overhaul, removed internal behaviour)
- **MINOR** - backward-compatible new functionality
- **PATCH** - backward-compatible bug fixes

The application version is **independent** of the API version.

An application major bump does not necessarily coincide with an API version bump, and vice versa.

Internal refactors, dependency upgrades, or infrastructure changes may warrant a new application MAJOR while the API contract stays on v1.

## Backend

The backend follows a **layered architecture** pattern:

---

### API layer (`app/api/`)

- HTTP request/response handling
- Route definitions and parameter validation
- Authentication/authorization enforcement
- Transaction boundary via `get_async_db` dependency (auto-commit on success, rollback on exception)

---

### Schemas layer (`app/schemas/`)

- Pydantic models for request/response validation
- Data serialization/deserialization
- camelCase aliases for JSON API (e.g. `activityId`, `areaId`, `postCode`)
- Validation (Layer 1: type/format validation)

---

### Service layer (`app/services/`)

- Business logic implementation
- Validation (Layer 2: business rules, e.g. area exists, platform lookup/creation)
- Raises `ApplicationValidationError` for domain-level errors (e.g. area not found)
- Does not commit or roll back transactions directly (delegated to API layer)

---

### CRUD layer (`app/crud/`)

- Database operations (Create, Read, Update, Delete)
- Data access abstraction
- SQLAlchemy query construction
- Uses flush (not commit) - defers transaction control to upper layers

---

### Models layer (`app/models/`)

- SQLAlchemy ORM models
- Database table definitions
- Relationships and constraints
- Includes `audit_log.py` for audit trail

For key patterns, see also [Internal data model](./DATAMODEL_TECH.md), [Security](./SECURITY.md), and [API](./API_TECH.md).

---

### Request flow

```
POST /api/str/v1/activities/bulk (JSON body with activities array)
  │
  ├── API Layer (str/routers/activities_bulk_v1.py, v2: activities_bulk_v2.py)
  │   ├── verify_bearer_token() → auth checks (roles, claims)
  │   ├── ActivityBulkRequest (Pydantic) → validates wrapper (min 1, max 1000)
  │   └── get_async_db → auto-commit/rollback transaction
  │
  ├── Service Layer (activity_bulk.py) - Application-First Validation
  │   ├── Step 1: Per-item Pydantic validation via TypeAdapter
  │   ├── Platform resolution (once per batch, version on name change only)
  │   ├── Intra-batch dedup (last-wins)
  │   ├── Step 2: RI check → single SELECT for area IDs → Python dict
  │   │     └── STR v2: area must be regulated for activities, else NOK (regulation_error)
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
  ├── API Layer (areas.py)
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

GET /api/ca/v2/activities (bearer token, optional filter query params)
  │
  ├── API Layer (activities_v2.py)
  │   ├── verify_bearer_token() → auth checks (roles, claims)
  │   ├── activity_filters() → parse createdAtFrom/To, platformId, areaId
  │   │     └── invalid functional ID format → 400
  │   └── get_async_db_read_only → read-only session
  │
  ├── Handler (activity_handlers.py)
  │   └── list_activities(client, session, offset, limit, filters)
  │
  ├── Service Layer (activity.py)
  │   └── relay filters to CRUD
  │
  ├── CRUD Layer (activity.py)
  │   └── apply WHERE clauses for each provided filter (AND semantics)
  │
  └── Response: 200 + ActivityListResponse (camelCase JSON)
```

The listing endpoints follow both flows unchanged: the three bulk writes take the first
shape, the five audience reads the second. What differs per listing endpoint is in
[Listing (technical)](./LISTING_TECH.md#code-structure).

## Data

### ID management

**Technical IDs**

- Represent technical keys, on the **"inside"** (under the hood)
- These are used for referential integrity within the database

**Functional IDs**

- Represent business identifiers, on the **"outside"**
- Are client-provided (optional), or auto-provisioned otherwise (UUIDv4 RFC 9562)
- After a POST, functional IDs are always returned/made visible
- This allows them to be reused in subsequent submissions
- Functional IDs enable versioning (in combination with a timestamp)

https://datatracker.ietf.org/doc/rfc9562/

See later in this document for more info on IDs.

---

### Versioning

Recall the standard attribute pattern from the [internal datamodel](./DATAMODEL_TECH.md#overview):

- Technical id (`id`)
- Functional id (`<class name>Id`)
- Display name (`<class name>Name`)
- ... (other attributes)
- Creation timestamp (`createdAt`)
- Ended-at timestamp (`endedAt`) (soft-delete)

Versioning pattern:

- A write never updates an existing row in place. Instead:
  - the current row is closed by setting its `endedAt`
  - a new row is inserted with a new `createdAt`
  - this means every change creates a new version
- For each functional id (e.g. an `areaId`) and owner (e.g. the CA that submitted it), there can be at most one current version:
  - a current version is a row where `endedAt` is `null`
  - a partial unique index enforces this rule in the database
- The owner is the party that submitted the row:
  - for a CA or platform, the owner is the logged-in client (`clientId`)
  - for an area, the owner is the CA
  - for a listing or activity, the owner is the platform
- Areas, listings and activities belong to their owner:
  - a CA owns its areas
  - a platform owns its listings and activities
- SDEP finds these records using the owner's **functional id**:
  - `competentAuthorityId` for a CA
  - `platformId` for a platform
  - these ids stay the same across versions
- SDEP does **not** use the owner's technical database id for lookup:
  - the technical id changes whenever a new version of the owner is created
  - using it would therefore break ownership lookups after an owner changes
  - the technical database ids are solely used for referential integrity: a row points to another row by its technical id (foreign key, FK)
- Example:
  - suppose platform `P1` owns listing `L1`
  - to find that listing, SDEP looks for the current row with:
    - `listingId = L1`
    - `platformId = P1`
  - it does not look for a particular technical version of platform `P1`
- When an owner gets a new version, its related data is not lost:
  - for example, changing a platform's `client_name` creates a new platform version
  - the platform keeps the same `platformId`
  - its listings and activities can therefore still be found
  - the same applies to a CA and its areas
- Older rows keep pointing to the owner version that existed when those rows were written.
  - new rows point to the owner's current version
  - this preserves the history of which owner version was active at the time
- There is one race condition to be aware of:
  - two requests may try to create the first current version of the same new functional id at exactly the same time
  - only one can win because of the partial unique index
  - the other request receives HTTP `409 Conflict` and can retry
- See also the versioning rules in [Datamodel](./DATAMODEL_TECH.md#classes).

Versioned classes:

| Class              | Functional id          | One current row per     | Finds its owner by          |
| ------------------ | ---------------------- | ----------------------- | --------------------------- |
| CompetentAuthority | `competentAuthorityId` | `clientId`              | (owner is the login client) |
| Platform           | `platformId`           | `clientId`              | (owner is the login client) |
| Area               | `areaId`               | `areaId` + CA           | `competentAuthorityId`      |
| Listing            | `listingId`            | `listingId` + platform  | `platformId`                |
| Activity           | `activityId`           | `activityId` + platform | `platformId`                |

Example (area and activities):

1. CA submits an area: a new row, with a technical `id` and the functional `areaId`
2. STR gets the areas: this yields the functional `areaId`s
3. STR submits activities for these `areaId`s: each activity row references the current area row by FK (`activity.area_id` → `area.id`, the area's technical `id`)
4. CA gets its activities: this yields the activities of step 3
5. CA updates the area (same `areaId`): the area gets a new current row (new technical `id`, same `areaId`); the previous row is ended
6. CA gets its activities: this still yields the activities of step 3. They keep referencing the previous area row, but the read matches them through the CA's `client_id` and the functional `areaId`, not through the area's technical `id`
7. STR gets the areas: this yields the current (updated) area, with the same `areaId`
8. STR submits activities for the same `areaId`: these reference the new area row (FK to the new technical `id`)
9. CA gets its activities: this yields the activities of steps 3 and 8

---

### Deleting

---

Concept:

**Soft-Delete**

- When all versions of a functional ID have `endedAt` set, the entity is considered **deactivated**
- Creating a new version with a deactivated functional ID is rejected (HTTP 422)
- This prevents "resurrecting" soft-deleted entities
- The guard applies to: `competentAuthorityId`, `platformId`, `areaId` and `activityId`; listings have no guard, because a listing cannot be deleted

When e.g. an area is deleted, and the CA retrieves activities, then:

- The activities that were submitted for that area are still returned: they keep their FK to the (now ended) area row, and the read matches them through the CA's `client_id`, without filtering on the area's `endedAt`
- STR can no longer submit new activities for that `areaId`: only current areas are found, so these items are NOK (`not_found_error`)
- The CA cannot reuse that `areaId`: a new version of a deactivated `areaId` is rejected (HTTP 422)

---

**Hard-Delete**

Hard-delete removes a row from the database (as opposed to soft-delete, which sets `endedAt`).

When a parent row has child rows referencing it via a foreign key, the database must decide what to do with those children. The three standard behaviours are:

| Behaviour      | FK clause                                     | Effect                                                 | When to use                                                                                  |
| :------------- | :-------------------------------------------- | :----------------------------------------------------- | :------------------------------------------------------------------------------------------- |
| **Restricted** | `NO ACTION` / `RESTRICT` (PostgreSQL default) | Parent delete is **blocked** if children exist         | When children must not exist without their parent, and accidental deletion must be prevented |
| **Nullified**  | `ON DELETE SET NULL`                          | Child FK column is set to `NULL`; children survive     | When children can exist independently (optional relationship)                                |
| **Cascaded**   | `ON DELETE CASCADE`                           | Children are **automatically deleted** with the parent | When children have no meaning without their parent (composition)                             |

**Current implementation:**

All foreign keys use the PostgreSQL default (`NO ACTION`), which is **restricted delete**:

| Parent             | Child         | FK column                     | Hard-delete behaviour                    |
| :----------------- | :------------ | :---------------------------- | :--------------------------------------- |
| CompetentAuthority | Area          | `area.competent_authority_id` | Restricted - blocked if Areas exist      |
| Area               | Activity      | `activity.area_id`            | Restricted - blocked if Activities exist |
| Platform           | Activity      | `activity.platform_id`        | Restricted - blocked if Activities exist |
| Area               | Listing       | `listing.area_id`             | Restricted - blocked if Listings exist   |
| Platform           | Listing       | `listing.platform_id`         | Restricted - blocked if Listings exist   |
| Activity           | *(leaf node)* | -                             | Unrestricted - deletes cleanly           |
| Listing            | *(leaf node)* | -                             | Unrestricted - deletes cleanly           |

In practice, the application uses **soft-delete** (`mark_as_ended`) for all operations. Hard-delete functions are not provided.

---

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
- `Listing` bulk versioning (the three listing bulk POSTs: submit, screen, acknowledge)
- `Activity` bulk versioning (bulk POST)

---

**Behaviour During Concurrent Requests**

If two requests attempt to version the same entity at the same time:

1. The first request acquires the row lock
2. The second request waits until the first transaction commits
3. The second request then continues safely using the updated state

A lock needs an existing row. The first write of a new functional ID (or the first contact of a new platform) has no row to lock yet. There the partial unique index on the current row decides: of two such writes at the same moment, one commits and the other gets HTTP 409 (`conflict_error`) and can retry, which then versions the committed row. The same holds for every versioned class, see [Datamodel](./DATAMODEL_TECH.md#classes).

Together, this guarantees consistent versioning without duplicate active records.

---

**Performance Considerations - Single-entity versioning**

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

**Performance Considerations - Bulk activity versioning**

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

- ~50-200 ms, depending on batch size

Likelihood of contention - only occurs when:

- Two bulk requests originate from the **same platform**
- Both contain overlapping activity IDs
- Both are submitted simultaneously

Different platforms never block each other because queries are filtered by `platformId`.

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

---

### Tenant isolation

Each tenant - a Competent Authority (CA) for areas, or a Platform (STR) for listings and activities - can only affect its own data. Isolation is enforced at multiple layers: JWT identity, service-layer scoping, CRUD-layer filtering, and database constraints.

Listings add a second dimension: several audiences read the same rows. There the read scope is fixed by the router per audience, never by a query parameter, so a caller cannot widen what it sees.

---

**Area operations (CA-scoped)**

- **Create / update (versioning):** The `mark-as-ended` + `create-new-version` lookup is scoped to the authenticated CA via `get_by_area_id_and_competent_authority_id_str()` with `SELECT ... FOR UPDATE`. Another CA may hold an area with the same `areaId` - it is not affected.
- **Delete (soft-delete):** Scoped lookup by `(areaId, competentAuthorityId)`. If the area belongs to a different CA, the operation returns 404.
- **Deactivation guard:** `exists_any_by_area_id()` is CA-scoped. A deactivated `areaId` from one CA does not block another CA from using the same `areaId`.
- **DB constraint:** `UNIQUE(area_id, competent_authority_id, created_at)` allows the same `areaId` to be used independently by different CAs.

---

**Activity operations (platform-scoped)**

- **Create / update (bulk versioning):** `get_current_by_activity_ids()` and `bulk_mark_as_ended()` both filter by the public `platformId`, across every version of that platform. Platform-A cannot version Platform-B's activities, even if they share the same `activityId`.
- **Delete:** No delete endpoint exists for activities.
- **DB constraint:** `UNIQUE(activity_id, platform_id, created_at)` allows the same `activityId` to be used independently by different platforms.
- **Deactivation guard:** `get_deactivated_activity_ids()` is platform-scoped, as the Area guard is CA-scoped, and is called on every bulk submission. However, no code path currently puts an activity into a deactivated state - there is no DELETE endpoint, and versioning always creates a new current version. The guard is defensive: if a DELETE endpoint is added in the future, it will prevent resurrection of deactivated activities. Compare with the equivalent Area guard (`exists_any_by_area_id`), which can trigger because areas can be soft-deleted via `DELETE /ca/areas/{areaId}`.

---

**Listing operations (platform-scoped write, audience-scoped read)**

- **Create / update (bulk versioning):** `get_current_by_listing_ids()` and `bulk_mark_as_ended()` both filter by the public `platformId`, across every version of that platform. Platform-A cannot version Platform-B's listings, even if they share the same `listingId`.
- **Screening and acknowledgement:** both carry the `createdAt` of the version they refer to, checked on the locked current version. A stale token is refused per item (`conflict_error`), so one actor's write never lands on another actor's version.
- **Screening scope:** the LSA writes for any platform, but it names the platform in its payload; the lookup still resolves through `platform_id`, so a screening cannot cross to another platform's listing by `listingId` alone.
- **Read:** the router fixes the `ListingScope` from the bearer token - `platform_client_id` for STR, `competent_authority_client_id` for CA, neither for LSA/LMA/STA - plus a fixed lifecycle status per audience. The scope is keyword-only with no default, so an unscoped read has to be written out.
- **Delete:** no delete endpoint exists for listings.
- **DB constraint:** `UNIQUE(listing_id, platform_id, created_at)` allows the same `listingId` to be used independently by different platforms.

---

**Enforcement layers**

| Layer       | Area                                                       | Activity                                                   | Listing                                                           |
| :---------- | :--------------------------------------------------------- | :--------------------------------------------------------- | :---------------------------------------------------------------- |
| **JWT**     | `client_id` identifies the CA                              | `client_id` identifies the platform (STR)                  | `client_id` identifies the platform (STR) or the reading audience |
| **API**     | Passes `client.id` to service; not overridable by the body | Passes `client.id` to service; not overridable by the body | Router fixes the `ListingScope`; no filter can widen it           |
| **Service** | Scoped lookups via `competent_authority_id_str`            | Scoped lookups via `platform_id`                           | Scoped lookups via `platform_id`, plus the version token          |
| **CRUD**    | WHERE clauses include `competent_authority_id`             | WHERE clauses include `platform_id`                        | WHERE clauses include `platform_id` and/or the scope joins        |
| **DB**      | `UNIQUE(area_id, competent_authority_id, created_at)` + FK | `UNIQUE(activity_id, platform_id, created_at)` + FK        | `UNIQUE(listing_id, platform_id, created_at)` + FK                |

---

### Lazy loading

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

`crud/listing.py` uses the same pattern, loading `Listing.platform` and
`Listing.area` (with its competent authority) at query time.

---

### Data flow

What each write does to the data, step by step and field by field, is documented per
resource, next to the rest of that resource's design:

- [Area](./AREA_TECH.md#data-flow) - `POST /areas` and `DELETE /areas/{areaId}`
- [Activity](./ACTIVITY_TECH.md#data-flow) - `POST /activities/bulk`
- [Listing](./LISTING_TECH.md#data-flow) - the three listing writes

All three follow the same shape, described above: validate, resolve references, version
under lock, commit at the API transaction boundary. The reads add nothing to the data;
they apply the scope and the filters, see [API](./API_TECH.md#filtering).

## Transactions

Two session factories handle different operation types:

| Dependency               | Session Type                | Transaction                                   | Used by                   |
| ------------------------ | --------------------------- | --------------------------------------------- | ------------------------- |
| `get_async_db`           | Write (autoflush=True)      | Auto-commit on success, rollback on exception | POST and DELETE endpoints |
| `get_async_db_read_only` | Read-only (autoflush=False) | No transaction overhead                       | GET endpoints             |

Write endpoints use `get_async_db`, which wraps the endpoint function in a single transaction. If any error occurs, the entire operation is rolled back. On success, the transaction is committed automatically.

The commit must happen before the response is sent, so a 2xx means the data is stored:

- Declare the session as `Depends(get_async_db, scope="function")`
- The FastAPI default (`scope="request"`) runs the commit after the response is sent. A client can then get `201`, read the resource back and get `404`, or get `201` for data that a failed commit never stored.
- The session is closed when the endpoint function returns, so build the response inside the function (`JSONResponse`, `Response`), not from ORM objects that need the session afterwards.
- `backend/tests/api/test_write_session_scope.py` fails the build for a route that uses the default scope.

## Validations

Validation is distributed across three layers, each with a distinct responsibility.

---

### Layers

| Layer                             | Responsibility                                              | Mechanism                                           | Example                                                              |
| --------------------------------- | ----------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------- |
| **Schemas (Pydantic)**            | Syntax: types, formats, lengths, patterns                   | Pydantic `Field()` constraints and type annotations | `activityId` must match `^[A-Za-z0-9-]+$`, max 64 chars              |
| **Service**                       | Business rules: referential integrity, state checks         | Python logic, database lookups                      | Area must exist, deactivated entities cannot be resubmitted          |
| **Model (SQLAlchemy/PostgreSQL)** | Data integrity: uniqueness, foreign keys, check constraints | Database constraints, model defaults                | Unique constraint on `(area_id, competent_authority_id, created_at)` |

---

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

---

### Functional IDs (user-supplied)

**Area and Activity functional IDs** are user-supplied.

These IDs are submitted by the caller in the request body or form fields and validated **declaratively by Pydantic** before the endpoint function body runs:

| Endpoint                           | Field                 | Type                   | Pydantic validates?                                       | When omitted                                                |
| ---------------------------------- | --------------------- | ---------------------- | --------------------------------------------------------- | ----------------------------------------------------------- |
| `POST /api/ca/v1/areas`            | `areaId` (form field) | `OptionalFunctionalId` | Yes - `Annotated[OptionalFunctionalId, Form()]`           | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |
| `POST /api/str/v2/listings/bulk`   | `listingId` per item  | `OptionalFunctionalId` | Yes - via `TypeAdapter(ListingRequest)` in service layer  | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |
| `POST /api/str/v1/activities/bulk` | `activityId` per item | `OptionalFunctionalId` | Yes - via `TypeAdapter(ActivityRequest)` in service layer | UUID generated by SQLAlchemy model default (`uuid.uuid4()`) |

**Why `POST /api/ca/v1/areas` uses `Form()` instead of a JSON body** (see implementation):

- `POST /api/ca/v1/areas` accepts **multipart/form-data** (required for file upload), so each field is an individual `Form()` parameter
  - The `Annotated[OptionalFunctionalId, Form()]` type annotation ensures Pydantic still validates the form field declaratively, just like JSON body fields
- `POST /api/str/v1/activities/bulk` accepts a JSON body; per-item validation is done via `TypeAdapter(ActivityRequest)` in the service layer

---

### Owner IDs and JWT client IDs

**Platform and Competent Authority public functional IDs** are generated UUID strings stored in `platform.platform_id` and `competent_authority.competent_authority_id`.

These public owner IDs are returned as `platformId` and `competentAuthorityId` in API responses. They are not supplied in request payloads and are not derived from JWT usernames or client identifiers.

The JWT token's `client_id` claim is stored separately in the private `client_id` column on `Platform` and `CompetentAuthority`. Service and CRUD code use this private value for lookup, ownership scoping, versioning, and deactivation checks.

| Endpoint                                         | Router                                    | JWT claim used for scoping   | Public owner ID exposed in responses |
| ------------------------------------------------ | ----------------------------------------- | ---------------------------- | ------------------------------------ |
| `POST /api/ca/v1/areas`                          | `areas.py`                                | `client_id`                  | `competentAuthorityId`               |
| `GET /api/ca/v1/areas`                           | `areas_list_v1.py`                        | `client_id`                  | `competentAuthorityId`               |
| `GET /api/ca/v2/areas`                           | `areas_list_v2.py`                        | `client_id`                  | `competentAuthorityId`               |
| `GET /api/ca/v1/areas/count`                     | `areas.py`                                | `client_id`                  | n/a                                  |
| `GET /api/ca/v1/areas/{areaId}`                  | `areas.py`                                | `client_id`                  | n/a                                  |
| `DELETE /api/ca/v1/areas/{areaId}`               | `areas.py`                                | `client_id`                  | n/a                                  |
| `POST /api/str/v2/listings/bulk`                 | `str/listings_bulk_v2.py`                 | `client_id`                  | `competentAuthorityId`, `platformId` |
| `GET /api/str/v2/listings`                       | `str/listings_v2.py`                      | `client_id`                  | `competentAuthorityId`, `platformId` |
| `POST /api/str/v2/listing-acknowledgements/bulk` | `str/listing_acknowledgements_bulk_v2.py` | `client_id`                  | `competentAuthorityId`, `platformId` |
| `GET /api/lsa/v2/listings`                       | `lsa/listings_v2.py`                      | none (roles only, unscoped)  | `competentAuthorityId`, `platformId` |
| `POST /api/lsa/v2/listing-screenings/bulk`       | `lsa/listing_screenings_bulk_v2.py`       | none (`platformId` per item) | `competentAuthorityId`, `platformId` |
| `GET /api/ca/v2/listings`                        | `ca/listings_v2.py`                       | `client_id`                  | `competentAuthorityId`, `platformId` |
| `GET /api/lma/v2/listings`                       | `lma/listings_v2.py`                      | none (roles only, unscoped)  | `competentAuthorityId`, `platformId` |
| `GET /api/sta/v2/listings`                       | `sta/listings_v2.py`                      | none (roles only, unscoped)  | `competentAuthorityId`, `platformId` |
| `GET /api/ca/v1/activities`                      | `activities_v1.py`                        | `client_id`                  | `competentAuthorityId`, `platformId` |
| `GET /api/ca/v1/activities/count`                | `activities_v1.py`                        | `client_id`                  | n/a                                  |
| `GET /api/ca/v2/activities`                      | `activities_v2.py`                        | `client_id`                  | `competentAuthorityId`, `platformId` |
| `GET /api/ca/v2/activities/count`                | `activities_v2.py`                        | `client_id`                  | n/a                                  |
| `POST /api/str/v1/activities/bulk`               | `str/activities_bulk_v1.py`               | `client_id`                  | `competentAuthorityId`, `platformId` |
| `POST /api/str/v2/activities/bulk`               | `str/activities_bulk_v2.py`               | `client_id`                  | `competentAuthorityId`, `platformId` |
| `GET /api/sta/v1/activities`                     | `sta/activities_v1.py`                    | none (roles only, unscoped)  | `competentAuthorityId`, `platformId` |
| `GET /api/sta/v1/activities/count`               | `sta/activities_v1.py`                    | none (roles only, unscoped)  | n/a                                  |
| `GET /api/ama/v1/activities`                     | `ama/activities_v1.py`                    | none (roles only, unscoped)  | `competentAuthorityId`, `platformId` |

The private `client_id` is never serialized in public API responses, OpenAPI examples, or public documentation as an owner ID.

## Exceptions

All exceptions are handled by global exception handlers:

- Defined in `app/exceptions/handlers.py`, and
- Registered in `app/api/common/exception_handlers.py`

The table below maps **application exceptions** to **HTTP status codes**:

| Application Exception                 | Description                                                                                                                                            | HTTP Status Code                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| `RequestValidationError`              | Invalid query parameters on a GET request (e.g. `offset=-1` or `limit=abc`)                                                                            | 400                               |
| `HTTPException`                       | Missing/invalid token claims, missing roles, missing credentials, inline input validation, resource not found, oversized upload (see `upload_size.py`) | 400 / 401 / 403 / 404 / 413 / 422 |
| `InvalidTokenError`                   | Invalid token (subtype of AuthenticationError)                                                                                                         | 401                               |
| `AuthenticationError`                 | Invalid or expired token                                                                                                                               | 401                               |
| `AuthorizationError`                  | Insufficient permissions                                                                                                                               | 403                               |
| `ResourceNotFoundError`               | Resource not found                                                                                                                                     | 404                               |
| `DuplicateResourceError`              | Duplicate resource conflict                                                                                                                            | 409                               |
| `IntegrityError` (unique violation)   | A concurrent request wrote the same current row first; other integrity errors are 500                                                                  | 409                               |
| `RequestValidationError`              | Invalid request body on a POST request (e.g. missing required field or wrong value type)                                                               | 422                               |
| `ApplicationValidationError`          | Business rule violations (e.g. start time later than end time is NOK )                                                                                 | 422                               |
| `Exception`                           | Catch-all (unexpected code failure)                                                                                                                    | 500                               |
| `DatabaseOperationalError`            | Database temporarily unavailable                                                                                                                       | 503                               |
| `AuthorizationServerOperationalError` | Authorization server temporarily unavailable (also a Keycloak 5xx on `/token`)                                                                         | 503                               |
| `MalwareScannerOperationalError`      | Malware scanner (ClamAV) could not complete the scan of an upload                                                                                      | 503                               |

*For the complete list of HTTP status codes used by the API, see [HTTP status codes](API_TECH.md#http-status-codes).*

## Bulk

The bulk endpoint `POST /api/str/v1/activities/bulk` is the single entry point for all STR activity submissions. The three listing bulk endpoints (`POST /listings/bulk`, `POST /listing-screenings/bulk`, `POST /listing-acknowledgements/bulk`, see [Listing (technical)](./LISTING_TECH.md)) follow the same design; where they differ (state preconditions, the `createdAt` version token, `conflict_error`) is described there.

---

### Approach

At high volumes (500K-4M records/day, ~6-46 records/second average), PostgreSQL is not the bottleneck - a standard Postgres instance can process thousands of transactions per second. The actual bottlenecks are:

1. **Network latency** - solved by batching 500-1000 items per API call
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

---

### Validation flow

Every bulk endpoint validates in the application layer, not in the database. Instead of
having the database check each record via savepoints:

- Application-level Pydantic validation is **many times faster** than database savepoints
- **Horizontally scalable**: add more API nodes under load
- **Single reference query per batch** (not per record)
- Only "clean" (validated) data reaches the database
- No savepoints or nested transactions needed, which avoids the overhead of extra database round-trips

The four steps, the same for the activity write and the three listing writes:

| Step                               | What                                                                                       | How                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| **1. Pydantic check**              | Validate each item against its request schema; a failed item is NOK with the error reason  | `TypeAdapter(<Item>Request).validate_python()` per item               |
| **2. Referential integrity check** | Fetch every referenced ID in one query into a `dict` (O(1) lookup); an unknown ID is NOK   | one `SELECT ... WHERE ... IN (...)` per batch                         |
| **3. Versioning under lock**       | Lock the current version, check the preconditions on it, mark it ended and insert the next | `SELECT ... FOR UPDATE`, then one `UPDATE` and one multi-row `INSERT` |
| **4. Feedback**                    | Per-item OK/NOK response in the original order **[1]**                                     | JSON response with summary counts                                     |

[1] Each item carries the batch-item `status` and either the embedded resource (OK) or an `errors` object (NOK). An embedded activity or listing also carries its own lifecycle `status`.

**Why step 2 after step 1:** it prevents unvalidated (untrusted) data from being used in
database operations.

**Why the step-3 checks must run on the locked row:** a state change creates a new version,
so a value read before the lock would be stale. Activities have no precondition beyond the
deactivation guard; listings check the state and the version token there, see
[Concurrency](./LISTING_TECH.md#concurrency).

What each write does per field is in the resource documents:
[Area](./AREA_TECH.md#data-flow), [Activity](./ACTIVITY_TECH.md#data-flow),
[Listing](./LISTING_TECH.md#data-flow).

---

**Contract versus runtime**

The wire contract (OpenAPI) and the runtime validation behaviour are deliberately decoupled.
`ActivityBulkRequest` is the worked example below; `ListingBulkRequest`,
`ListingScreeningBulkRequest` and `ListingAcknowledgementBulkRequest` work identically.

- **Contract (OpenAPI)** - `ActivityBulkRequest.activities` is typed concretely as `list[ActivityRequest]`, so the spec documents the full item shape instead of an untyped object.
- **Runtime** - items are *not* validated at request-parse time. If Pydantic validated the whole list eagerly, one bad item would return HTTP 422 for the entire batch and the per-item OK/NOK flow would be unreachable.

Implementation:

- The field is declared as `list[SkipValidation[ActivityRequest]]`
  - `SkipValidation` keeps the declared type for JSON-schema generation but replaces the runtime validator with a pass-through
  - So items arrive at the service layer as raw dicts
  - Exactly what step 1 (`TypeAdapter(ActivityRequest).validate_python()` per item) expects
- Because `SkipValidation` makes FastAPI's model-discovery pass treat the field as a leaf, `ActivityRequest` is **not** auto-registered in `components.schemas`
  - FastAPI inlines its schema into `items`
  - A post-processing hook in `app/api/common/openapi.py` (`extract_bulk_item_schemas`, one table row per bulk request) lifts the inlined schema out and replaces the inline with a `$ref` to `#/components/schemas/ActivityRequest`, restoring it as a reusable named component
  - This follows the same pattern already used in that file for renaming `Body_*` schemas

Result:

- The contract is schema-concrete and reusable, for every bulk request
- Runtime behaviour preserves per-item NOK feedback unchanged

---

### Status codes

| HTTP Status                   | When                                                                |
| ----------------------------- | ------------------------------------------------------------------- |
| **201 Created**               | All items created successfully (`failed == 0`)                      |
| **200 OK**                    | Partial success: some OK, some NOK (`succeeded > 0 AND failed > 0`) |
| **422 Unprocessable Content** | All items failed validation (`succeeded == 0`)                      |

---

### Design decisions

| #       | Decision                                                                                                                                   | Rationale                                                                                            |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| **D1**  | **Per-item Pydantic validation** - the request accepts raw dicts, each validated individually in the service layer                         | One invalid item must not block the other (999) items in the batch                                   |
| **D2**  | **Intra-batch duplicates: last-wins** - of a repeated functional ID in one batch only the last is processed, the others are NOK            | Deterministic for clients, no ambiguity about which version wins; extends across requests **[1]**    |
| **D3**  | **Versioning: batch UPDATE before INSERT** - current versions are ended with one `UPDATE ... WHERE <id> IN (...)` first                    | Same semantics as single-endpoint versioning, with 1 UPDATE + 1 INSERT instead of per-item queries   |
| **D4**  | **Platform resolution: version only on name change** - resolved once per platform-owned batch, a new version only if `client_name` changed | No versioning churn when one platform submits many batches with unchanged credentials                |
| **D5**  | **Deactivated entities rejected** - a functional ID whose versions all have `endedAt` set is NOK when submitted again                      | No "resurrecting" of soft-deleted entities; consistent with the single endpoint                      |
| **D6**  | **No `ON CONFLICT DO NOTHING`** - explicit versioning (mark-as-ended + new insert) instead of a database-level upsert                      | The upsert is a common idempotency practice, but the data model needs explicit `endedAt` versioning  |
| **D7**  | **Single transaction scope** - the whole bulk operation is one transaction; a failed INSERT rolls everything back                          | No partial database state; consistent with the `get_async_db` auto-commit/rollback model             |
| **D8**  | **SQLite compatibility** - the bulk INSERT and all queries work on PostgreSQL and SQLite                                                   | Unit tests run on in-memory SQLite; the `StringArray` TypeDecorator handles dialect differences      |
| **D9**  | **Lifecycle status on activities** - `status` is `finished` (default) or `cancelled`; resubmitting as `cancelled` adds a version           | Platforms correct previously submitted stays without a change to the versioning model                |
| **D10** | **State precondition and version token on listing writes** - refused per item on a wrong state or a stale `createdAt` **[2]**              | Several actors write the same listing asynchronously; one version's flags must never land on another |

[1] Combined with pessimistic locking ([Locking](#locking)): when two concurrent batches contain the same `activityId`, `SELECT ... FOR UPDATE` serializes them, so the second batch waits for the first to commit and then overwrites it. Last-wins holds within a batch and across requests.

[2] The check runs on the locked current version: the state must be the one the write expects, and the submitted `createdAt` must still be current. D1 to D8 hold unchanged for the three listing bulk endpoints. D9 has no listing equivalent: a listing's `status` is not set by the caller but derived from the write, see [Transitions](./LISTING_TECH.md#transitions). D10 is the one concept activities do not have, because an activity has a single writer (the platform) while a listing has three (platform, LSA, platform again).
