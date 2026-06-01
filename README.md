<h1>Welcome to the Single Digital Entry Point (SDEP)</h1>

Overview:

- [Introduction](#introduction)
- [Specification](#specification)
- [Reference Implementation](#reference-implementation)
- [Production](#production)
- [Pre-production Testing](#pre-production-testing)
- [Development](#development)
  - [Fullstack](#fullstack)
  - [Tests (Unit)](#tests-unit)
  - [Tests (Fullstack)](#tests-fullstack)
  - [Tests (Performance)](#tests-performance)
  - [All Tests](#all-tests)
  - [Security](#security)
  - [All Tests + Security](#all-tests--security)
- [Functional Design](#functional-design)
- [Technical Design](#technical-design)
- [Process](#process)
- [Foundation](#foundation)

## Introduction

SDEP is established in accordance with EU legislation for short-term rental data exchange.

https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng

In accordance with EU legislation, SDEP enables the following:

- **Ingestion of regulated areas** from competent authorities (CA)
- **Provision of regulated areas** to short-term rental platforms (STR)
- **Ingestion of rental-activity data** from short-term rental platforms (STR)
- **Provision of rental-activity data** to competent authorities (CA) and other stakeholders
- **Ingestion of flagged listings** from short-term rental platforms (STR)
- **Provision of flagged listings** to relevant stakeholders

> **Note**: Support for flagged listings is currently under development.

## Specification

This repository contains the **API specification** for SDEP implementations across EU Member States.

The short-term rental component (**STR**) is **EU-harmonized** across SDEP implementations in EU Member States.

The competent authority component (**CA**) is provided as **guidance and recommendation only** and may differ between EU Member States.

## Reference Implementation

This repository contains the **EU reference implementation** for SDEP implementations across EU Member States.

The implementation is provided as **guidance only** and can serve as a **blueprint** for national implementations.

The implementation may differ between EU Member States.

## Production

The reference implementation is deployed in production (**PRD**) in the Netherlands as **SDEP-NL**.

To get started, see: [PRD](./docs/GET_STARTED_PRD.md).

The PRD environment (https://sdep.gov.nl/api/docs):

- Enables competent authorities (CA) and short-term rental platforms (STR) in the Netherlands to exchange regulated-area and rental-activity data in accordance with EU legislation
- Includes the **EU-harmonized short-term rental (STR) component**
- Includes the **SDEP-NL-specific competent authority (CA) component**

> **Disclaimer (PRD)**: For production use in your own country, always contact your **national SDEP representative** regarding national deployment and operational responsibilities.

## Pre-production Testing

To facilitate end-to-end testing with integration partners, the reference implementation is also deployed in a dedicated pre-production environment (**PRE**) in the Netherlands within SDEP-NL.

To get started, see: [PRE](./docs/GET_STARTED_PRE.md).

The PRE environment (https://pre-sdep.minvro.nl/api/docs):

- Enables integration partners to test integrations with the **EU-harmonized short-term rental (STR) component** before connecting to production systems
- Also provides testing access to the **SDEP-NL-specific competent authority (CA) component**

In the PRE environment:

- Only anonymized data should be used
- A daily cleanup takes place to remove any residual test or production-like data

> **Disclaimer (PRE)**: For end-to-end testing in your own country, always contact your **national SDEP representative** for guidance on deployment, integrations, and operations.

## Development

The reference implementation can be developed and tested **fullstack** on a local workstation.

*Tested on Linux; for Windows, consider using WSL.*

### Fullstack

**Prerequisites**

Required:

- Docker
- "jq" and "yq"
- "make"
- "uv" (includes uvx)

Optional:

- DBGate (a PostgreSQL management tool)

**Clone this repo**

To your local workstation.

**Run SDEP (fullstack)**

Incl. local infra (postgres + keycloak + backend):
```
make up
```

Default ports for the started services are defined in `.env`

- To override any of these values, define them in `.env.extra`
- See example in `.env.extra.example`

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

### Tests (Unit)

Backend only:
```
cd backend
make test
```

### Tests (Fullstack)

Fullstack (invoke from top-level):
```
make test-full
```

The tests cover the cases as described in the [integration test documentation](./docs/INTEGRATION_TESTS.md).

- Tests are executed against the complete Dockerized stack
- Test suites run sequentially: `test-smoke`, `test-security`, `test-str`, and `test-ca` - each exercising the live API over HTTP (curl, and httpx for the STR bulk endpoint)
- Test data uses the `sdep-test-*` naming convention; this data is automatically detected and removed after each test run (`postgres/clean-testrun.sql`)
- Test isolation is enforced by comparing table row counts before and after execution (PRE/POST); any discrepancy causes the build to fail
- A consolidated summary report presents per-suite and overall totals (executed/passed/failed) and exits with a non-zero status if any test fails

Malware scanning (ClamAV) is part of the fullstack tests and is run as a separate command (it is not included in `make test-full`):
```
make test-malware
```

All fullstack tests can also be re-used/run against real deployments (TST, ACC, PRE, PRD; contact SDEP NL for more info).

### Tests (Performance)

Locust-based load testing for the bulk activity endpoint (`POST /str/activities/bulk`).
```
make test-perf
```

For full configuration options and usage examples, see [Performance Tests](./docs/PERFORMANCE_TESTS.md).

### All Tests

All tests in one go (fullstack + performance):
```
make test
```

This runs the fullstack tests (`test-full` and the malware scan `test-malware`), followed by the performance test (`test-perf`).

### Security

Scan the backend image for known CVEs:

```
make trivy
```

This check:

- Builds the backend image from scratch with `--pull --no-cache`
  - This ensures the latest Debian security updates are included.
  - Cached layers can otherwise retain vulnerabilities that have already been fixed upstream.
- Scans the resulting image with Trivy via the `run-trivy-scan` Compose service.
- Compares findings against the allowlist in a `docs/CVE_EXPLAINS.md` and fails if:
  - New CVEs are detected that are not allowlisted.
  - Allowlisted CVEs are no longer present and should be removed from the file.

The `docs/CVE_EXPLAINS.md` is not checked-in.

- Each EU member state implementing an SDEP is responsible for monitoring and remediating CVEs within its own CI/CD

The scan uses a temporary image tag and does not affect the image used by `make up`.

OS security updates are applied by `apt-get upgrade` in the Dockerfile, but those updates are only incorporated when the layer is rebuilt.

- For fast local development, `make up` reuses Docker's build cache
  - Image is not guaranteed to include the latest security patches.
- In CI/CD guarantee, a fully up-to-date image should be guaranteed by disable caching
  - For example, `--cache=false`
- In the Trivy security gate (`make trivy`), a fully up-to-date image is also guaranteed
  - See the above `--pull --no-cache`.

To refresh a local image on demand:

```bash
make trivy
# or
docker compose build --pull --no-cache backend
```

### All Tests + Security

```
make all
```

## Functional Design

- [Architecture](./docs/ARCHITECTURE_FUNC.md)
- [Listing and Activity](./docs/LISTING_ACTIVITY.md) (work in progress)

## Technical Design

- [Architecture](./docs/ARCHITECTURE_TECH.md)
- [Internal Data Model](./docs/DATAMODEL.md)
- [API](./docs/API.md)
- [Security](./docs/SECURITY.md)
- [Database Dialects](./docs/DATABASE_DIALECTS.md)
- [Development](./docs/DEVELOPMENT.md)

## Process

- [Way Of Working](./docs/WOW.md)

## Foundation

This repository builds upon the original foundational work provided by the **Short-Term Rental Application Profile and Prototype (STR-AP)** project:

https://github.com/SEMICeu/STR-AP
