<h1>Welcome to the Single Digital Entry Point (SDEP)</h1>

Overview:

- [Introduction](#introduction)
- [Specification](#specification)
- [Reference Implementation](#reference-implementation)
- [Production (PRD)](#production-prd)
- [Pre-production Testing (PRE)](#pre-production-testing-pre)
- [Development](#development)
  - [Fullstack](#fullstack)
  - [Tests (Unit)](#tests-unit)
  - [Tests (Fullstack)](#tests-fullstack)
  - [Tests (Migrations)](#tests-migrations)
  - [Tests (Performance)](#tests-performance)
  - [Tests (Security)](#tests-security)
  - [Tests (All)](#tests-all)
  - [Markdown](#markdown)
  - [All](#all)
- [Functional Design](#functional-design)
- [Technical Design](#technical-design)
- [Getting started](#getting-started)
- [Process](#process)
- [Foundation](#foundation)

## Introduction

SDEP is established in accordance with **EU legislation** for short-term rental data exchange.

https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng

In accordance with this legislation, SDEP supports the following capabilities:

- **Ingesting data on regulated areas** from competent authorities (CAs)
- **Providing data on regulated areas** to short-term rental platforms (STRs)
- **Ingesting rental activity data** from STRs
- **Providing rental activity data** to CAs and other relevant stakeholders
- **Ingesting flagged listing data** from STRs
- **Providing flagged listing data** to CAs and other relevant stakeholders
- **Supporting statistical reporting** to reporting/statistics offices (REPs) and other relevant stakeholders

> **Note**: Support for flagged listings and statistical reporting is currently under development.

## Specification

This repository contains the **API specifications** for SDEP implementations across EU Member States.

**Harmonized components**

- The short-term rental (**STR**) component is **harmonized at EU level**
- It is common to all SDEP implementations in EU Member States.

**National components**

- The competent authority (**CA**) and reporting/statistics (**REP**) components are provided as **guidance only**.
- Their implementation may vary between EU Member States to accommodate national legislation and administrative requirements.

## Reference Implementation

This repository contains the **EU reference implementation** for SDEP implementations (CA, STR, REP) across EU Member States.

The implementation is provided as **guidance only** and can serve as a **blueprint** for national implementations.

The implementation may differ between EU Member States.

## Production (PRD)

The reference implementation is deployed in production (**PRD**) in the Netherlands as **SDEP-NL**

- https://sdep.gov.nl/api/docs.

The production environment (PRD):

- Enables competent authorities (CA) and short-term rental platforms (STR) in the Netherlands to exchange regulated-area and rental-activity data in accordance with EU legislation
- Includes the **EU-harmonized** short-term rental (STR) component
- Includes the **SDEP-NL-specific** competent authority (CA) and reporting/statistics (REP) components

> **Disclaimer (PRD)**: For production use in your own country, always contact your **national SDEP representative** regarding national deployment and operational responsibilities.

For onboarding, see [Getting Started in PRD](./docs/GET_STARTED_PRD.md).

## Pre-production Testing (PRE)

To facilitate end-to-end testing with integration partners, the reference implementation is also deployed in a dedicated pre-production environment (**PRE**) in the Netherlands within SDEP-NL

- https://pre-sdep.minvro.nl/api/docs.

The pre-production environment (PRE):

- Enables integration partners to test integrations with the **EU-harmonized** short-term rental (STR) component before connecting to production systems
- Also provides testing access to the **SDEP-NL-specific** competent authority (CA) and reporting/statistics (REP) components

In the PRE environment:

- Only anonymized data should be used
- A daily cleanup takes place to remove any residual test or production-like data

For **onboarding**, see: [Getting Started in PRE](./docs/GET_STARTED_PRE.md).

> **Disclaimer (PRE)**: For end-to-end testing in your own country, always contact your **national SDEP representative** for guidance on deployment, integrations, and operations.

## Development

The reference implementation can be developed and tested **fullstack** on a local workstation.

*Tested on Linux; for Windows, consider using WSL.*

---

### Fullstack

---

**Prerequisites**

Required:

- Docker
- "jq" and "yq"
- "make"
- "uv" (includes uvx)

Optional:

- DBGate (PostgreSQL management)

---

**Clone this repo**

To your local workstation.

---

**Run SDEP (fullstack)**

Start Postgres + Keycloak + SDEP API (backend):

```
make up
```

*Default ports for the started services are defined in `.env`. To override any of these values, define them in `.env.extra` (see example in `.env.extra.example`).*

Explore API docs in Swagger UI:

- http://localhost:8000/api/docs

In Swagger UI, use **Authorize** to activate either of the following **client authentication methods** (both fall under the same **Client Credentials flow**, see also [Authentication and Authorization](./docs/SECURITY.md#authentication-and-authorization)):

- **Client ID & secret** ("client secret auth")

  - This is the default for testing (easier to use)
  - It uses **client-id & secret** to acquire a `Bearer` token, that is used in turn to invoke the other (authenticated) endpoints
  - See [machine-clients.yaml](./keycloak/machine-clients.yaml) for credentials & roles
  - Credentials for all roles are present, so you can replay all end-to-end scenarios (CA, STR, REP)

- **Client-signed JWT** ("client signed JWT auth")

  - This provides a more secure way to test production behavior
  - It uses **client-signed JWT** to acquire a `Bearer` token, that is used in turn to invoke the other (authenticated) endpoints
  - It requires an additional private/public keypair to generate the client-signed JWT
  - Credentials for all roles are explained in the guidance, so you can test how client-signed JWT authentication works for your role (CA, STR, REP)
  - It also requires you to disable client-secret authentication in your local `.env.extra` (consider a `make backend-restart` to effectuate):
    ```bash
    CLIENT_SECRET_AUTH_ENABLED=false
    ```
  - See [Client-Signed JWT Authentication](./docs/GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance

- National SDEP implementations are free to adopt either method in production

  - SDEP-NL supports both methods in pre-production (PRE)
  - SDEP-NL supports only client-signed JWT in production (PRD)

---

**Run SDEP (backend only)**

Start SDEP API (backend) only, excl. Postgres and Keycloak:

```
cd backend
make up
```

---

### Tests (Unit)

Backend:

```
cd backend
make test
```

---

### Tests (Fullstack)

Fullstack:

```
# Invoke from top-level
make test-full
```

The tests cover the cases as described in the [integration test documentation](./docs/INTEGRATION_TESTS.md).

- Tests are executed against the complete Dockerized stack
- Test suites run sequentially: `test-smoke`, `test-security`, `test-str`, `test-ca`, and `test-rep` - each exercising the live API over HTTP (Python `httpx`)
- Test data uses the `sdep-test-*` naming convention; this data is automatically detected and removed after each test run (`postgres/clean-testrun.sql`)
- Test isolation is enforced by comparing table row counts before and after execution (PRE/POST); any discrepancy causes the build to fail
- A consolidated summary report presents per-suite and overall totals (executed/passed/failed) and exits with a non-zero status if any test fails

> Fullstack tests can be re-used in Test or Production environments (contact team SDEP-NL for more info).

---

### Tests (Migrations)

Alembic migrations are verified separately against PostgreSQL:

```
make test-migrations
```

- Applies all migrations to an empty database (`make -C backend upgrade`)
- Verifies the resulting check constraints match the models
- Runs without the full stack, so it is also usable as a CI/CD pipeline gate

---

### Tests (Performance)

Locust-based load testing for the bulk activity endpoint (`POST /str/activities/bulk`).

```
make test-perf
```

For full configuration options and usage examples, see [Performance Tests](./docs/PERFORMANCE_TESTS.md).

---

### Tests (Security)

---

**Malware scan (ClamAV)**

Scan uploaded files for malware: `make test-malware`

- Connects directly to the ClamAV container (not the backend API).
- Runs standalone, so it can be used as a CI/CD security gate without starting the full stack.

---

**Vulnerability scan (Trivy)**

Scan the backend image for common vulnerabilities and exposures (CVEs): `make test-cve`

This command:

- Rebuilds the backend image from scratch (`--pull --no-cache`) to ensure the latest Debian security updates are included. Cached layers may otherwise retain vulnerabilities already fixed upstream.
- Scans the image with Trivy via the `run-trivy-scan` Compose service.
- Compares results against `docs/CVE_EXPLAINS.md` and fails if:
  - New CVEs are found that are not allowlisted.
  - Allowlisted CVEs are no longer present and should be removed.

The scan uses a temporary image tag and does not affect the image used by `make up`.

> **Note:** `docs/CVE_EXPLAINS.md` is intentionally not committed. Each EU member state implementing an SDEP is responsible for maintaining its own CVE allowlist and remediation process within its CI/CD pipeline.

---

**Keeping images up to date**

Security updates are installed via `apt-get upgrade` during the Docker build, so they are only applied when the relevant layer is rebuilt.

- `make up` reuses Docker's build cache for faster local development and therefore does **not** guarantee the latest security patches.
- CI/CD should always perform a clean rebuild (e.g. `--pull --no-cache`) before publishing or deploying images.
- `make test-cve` already performs such a clean rebuild, ensuring the scan runs against a fully up-to-date image.

To refresh your local backend image manually: `make test-cve` or `docker compose build --pull --no-cache backend`.

---

### Tests (All)

Test all in one go (fullstack + migrations + malware + performance):

```
make test
```

---

### Markdown

Markdown lint:

```
make md-lint
```

Markdown format:

```
make md-format
```

---

### All

All in one go:

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

## Getting started

- [Client-signed JWT authentication](./docs/GET_STARTED_CLIENT_SIGNED_JWT.md)
- [Pre-production](./docs/GET_STARTED_PRE.md)
- [Production](./docs/GET_STARTED_PRD.md)

## Process

- [Way Of Working](./docs/WOW.md)

## Foundation

This repository builds upon the original foundational work provided by the **Short-Term Rental Application Profile and Prototype (STR-AP)** project:

https://github.com/SEMICeu/STR-AP
