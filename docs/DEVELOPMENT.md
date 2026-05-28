<h1>Development</h1>

This document covers the development workflow, testing strategy, and key configuration files for the SDEP application.

For architecture and request flow, see [Technical Architecture](./ARCHITECTURE_TECH.md). \
For database dialect compatibility, see [Database Dialects](./DATABASE_DIALECTS.md).

<h2>Table of Contents</h2>

- [Development Workflow](#development-workflow)
- [Testing Strategy](#testing-strategy)
  - [Unit Tests](#unit-tests-backendtests)
  - [Integration Tests](#integration-tests-tests)
  - [Performance Tests](#performance-tests-testsperformance)
- [Key Configuration Files](#key-configuration-files)

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

### Performance Tests (`tests/performance/`)
- Locust-based load testing for the bulk activity endpoint (`POST /api/str/v1/activities/bulk`)
- Measures throughput (activities/sec), extrapolates capacity (activities/day), compares against configurable target
- Uses isolated test data (`sdep-test-perf-*` prefix) by default; optionally keeps data in database (`PERF_KEEP_DATA=true`)
- Configurable: `PERF_ACTIVITIES_TARGET` (total target volume), `PERF_USERS` (concurrent users to reach target), `PERF_MAX_DURATION_SECONDS`, `PERF_BATCH_SIZE`, `PERF_KEEP_DATA`
- **Run:** `make test-perf` (or e.g. `make test-perf PERF_USERS=5 PERF_ACTIVITIES_TARGET=1000000 PERF_MAX_DURATION_SECONDS=10`)
- See [Performance Tests](PERFORMANCE_TESTS.md) for detailed documentation

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
