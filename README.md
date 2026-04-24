<h1>Welcome to the Single Digital Entry Point (SDEP)</h1>

Overview:

- [Reference Implementation (production)](#reference-implementation-production)
- [Integration Partners (pre-production)](#integration-partners-pre-production)
- [Development (local)](#development-local)
- [Main functionality](#main-functionality)
- [Background](#background)
- [Unit tests](#unit-tests)
- [Integration tests](#integration-tests)
- [Performance tests](#performance-tests)
- [Functional design](#functional-design)
- [Technical design](#technical-design)
- [Process](#process)

## Reference Implementation (production)

The reference implementation for this repository is **SDEP Netherlands (NL)**.

**Production environment (PRD):** https://sdep.gov.nl/api/docs

> **Disclaimer**: The API is yet subject to change and may be updated **without versioning**.

## Integration Partners (pre-production)

The reference implementation is also available in a **pre-production environment (PRE)**, enabling integration partners to test their integrations with SDEP.

> **Warning**: You are supposed to use only anonimized data in PRE.

> **Disclaimer**: PRE is still cleaned daily to remove any potential residual production test data.

To get started, see: [PRE](./docs/PRE.md).

## Development (local)

The reference implementation can also be run **fullstack** on a local workstation.

*Tested on Linux; for Windows, consider using WSL.*

**Prerequisites**

Required:

- Docker
- "jq" and "yq"
- "make"

Optional:

- DBGate (a PostgreSQL management tool)
- "uvx" (a component used in performance testing)

**Clone this repo**

To your local workstation.

**Run SDEP (fullstack)**

Incl. local infra (postgres + keycloak + backend):
```
make up
```
Ports for the started services are defined in .env. To override any of these values, define them in .env.extra.

Explore API docs (Swagger UI):

- http://localhost:8000/api/docs

Select client credentials (by roles):

- Choose `id`, `secret` from [machine-clients.yaml](./keycloak/machine-clients.yaml)

Authorize in Swagger UI:

- Select Authorize
- Enter client credentials
- Select Authorize again
- Swagger will obtain a JWT bearer token "under the hood" (acting on the `token/` endpoint)
- You are authorized by roles

Explore endpoints in your current role (ca, str).


**Run SDEP (backend only)**

Excl. local infra:
```
cd backend
make up
```

**Explore all options**
```
make
```

## Main functionality

In accordance with EU legislation, SDEP enables the following:

- **Ingest regulated areas** from competent authorities (CA)
- **Provide regulated areas** to short-term rental platforms (STR)
- **Ingest rental activity data** from short-term rental platforms (STR)
- **Provide rental activity data** to competent authorities (CA) and other stakeholders
- **Ingest flagged listings** from short-term rental platforms (STR)
- **Provide flagged listings** to relevant stakeholders

*Support for flagged listings is currently under development.*

## Background

SDEP is required by EU legislation.

https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng

See also the Short Term Rental Application and Prototype Profile (STR-AP).

https://github.com/SEMICeu/STR-AP

## Unit tests

Backend only:
```
cd backend
make test
make test-verbose
```

## Integration tests

Fullstack:
```
make up
make test
make test-verbose
```

The tests cover the cases as described in the [integration test documentation](./docs/INTEGRATION_TESTS.md).

- Tests are executed against the complete Dockerized stack
- Test suites run sequentially: `test-security`, `test-str`, and `test-ca` - each exercising the live API via curl
- Test data uses the `sdep-test-*` naming convention; this data is automatically detected and removed after each test run (`postgres/clean-testrun.sql`)
- Test isolation is enforced by comparing table row counts before and after execution (PRE/POST); any discrepancy causes the build to fail
- A consolidated summary report presents per-suite and overall totals (executed/passed/failed) and exits with a non-zero status if any test fails

The tests can also be re-used/run against real deployments (TST, ACC, PRE, PRD; contact SDEP NL for more info).

## Performance tests

Locust-based load testing for the bulk activity endpoint (`POST /str/activities/bulk`).

Fullstack:
```
make up
make test-perf
```

For full configuration options and usage examples, see [Performance Tests](./docs/PERFORMANCE_TESTS.md).

## Functional design

- [Architecture](./docs/ARCHITECTURE_FUNC.md)
- [Listing and Activity](./docs/LISTING_ACTIVITY.md) (work in progress)

## Technical design

- [Architecture](./docs/ARCHITECTURE_TECH.md)
- [Internal datamodel](./docs/DATAMODEL.md)
- [API](./docs/API.md)
- [Security](./docs/SECURITY.md)

## Process

- [Way Of Working](./docs/WOW.md)
