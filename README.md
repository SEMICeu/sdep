<h1>Welcome to the Single Digital Entry Point (SDEP)</h1>

Overview:

- [Reference impl. (production)](#reference-impl-production)
- [Quick start (local workstation)](#quick-start-local-workstation)
- [Background](#background)
- [Main functionality](#main-functionality)
- [Unit tests](#unit-tests)
- [Integration tests](#integration-tests)
- [Design](#design)
- [Process](#process)

## Reference impl. (production)

The reference impl. for this repo is SDEP Netherlands:

https://sdep.gov.nl/api/v0/docs

DISCLAIMER - the API is yet subject to change (without versioning).

## Quick start (local workstation)

On a local workstation (tested on Linux; for Windows, consider using WSL).

**Pre-requistes**

- Docker installed
- "jq" and "yq" installed
- "make" installed

**Clone this repo**

To your local workstation.

**Run SDEP fullstack**

Incl. local infra (postgres + keycloak + backend):
```
make up
```

Explore API docs (Swagger UI):

- http://localhost:8000/api/v0/docs

Select client credentials (by roles):

- Choose `id`, `secret` from [machine-clients.yaml](./keycloak/machine-clients.yaml)

Authorize in Swagger UI:

- Select Authorize
- Enter client credentials
- Select Authorize again
- Swagger will obtain a JWT bearer token "under the hood" (acting on the `token/` endpoint)
- You are authorized by roles

Explore endpoints in your current role (ca, str).


**Run SDEP backend only**

Excl. local infra:
```
cd backend
make up
```

**Explore all options**
```
make
```

## Background

SDEP is required by EU legislation.

https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng

## Main functionality

Ingest and expose:

- To **ingest regulated areas** from competent authorities (CA)
- To **expose regulated areas** to short-term rental platforms (STR)
- To **ingest rental activities** from short-term rental platforms
- To **expose rental activities** to competent authorities and other stakeholders

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
make test
make test-verbose
```

The tests cover the cases as described [here](./tests/README.md).

- Tests are executed against the complete Dockerized stack
- Test suites run sequentially: `test-security`, `test-str`, and `test-ca` - each exercising the live API via curl
- Test data uses the `sdep-test-*` naming convention; this data is automatically detected and removed after each test run (`postgres/clean-testrun.sql`)
- Test isolation is enforced by comparing table row counts before and after execution (PRE/POST); any discrepancy causes the build to fail
- A consolidated summary report presents per-suite and overall totals (executed/passed/failed) and exits with a non-zero status if any test fails

The tests can also be re-used/run against real deployments (TST, ACC, PRE, PRD; contact SDEP NL for more info).

## Design

- [Datamodel](./docs/DATAMODEL.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Design log](./docs/DESIGN.md)

## Process

- [Way Of Working](./docs/WOW.md)
