<h1>Welcome to the Single Digital Entry Point (SDEP)</h1>

Overview:

- [Introduction](#introduction)
- [Specification](#specification)
- [Reference implementation](#reference-implementation)
- [Production (PRD)](#production-prd)
- [Pre-production testing (PRE)](#pre-production-testing-pre)
- [Development](#development)
  - [Fullstack](#fullstack)
  - [Tests (unit)](#tests-unit)
  - [Tests (fullstack, integration)](#tests-fullstack-integration)
  - [Tests (migrations)](#tests-migrations)
  - [Tests (performance)](#tests-performance)
  - [Tests (security)](#tests-security)
  - [Tests (all)](#tests-all)
  - [All](#all)
- [Design](#design)
  - [Style guide](#style-guide)
  - [Definitions](#definitions)
  - [Functional](#functional)
  - [Technical](#technical)
  - [Security](#security)
- [Getting started](#getting-started)
- [Known issues](#known-issues)
- [Process](#process)
- [Foundation](#foundation)

## Introduction

SDEP is established in accordance with **EU legislation** for short-term rental data exchange.

https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng

In accordance with this legislation, SDEP supports the following capabilities:

- **Ingesting regulated areas** from competent authorities (CAs)
- **Providing regulated areas** to short-term rental platforms (STRs)
- **Ingesting listings (random checks)** from STRs
- **Providing listings (random check results)** to CAs and other relevant stakeholders
- **Ingesting rental activities** from STRs
- **Providing rental activities** to CAs and other relevant stakeholders
- **Supporting statistical reporting** to statistics authorities (STAs) and other relevant stakeholders

## Specification

This repository contains the **API specifications** for SDEP implementations across EU Member States.

**Harmonized components**

- The short-term rental (**STR**) component is **harmonized at EU level**
- It is common to all SDEP implementations in EU Member States

**National components**

- The competent authority (**CA**), statistics authority (**STA**), listing screening authority (**LSA**) and monitoring authority (**LMA**, **AMA**) components are provided as **guidance only**
- Their implementation may vary between EU Member States to accommodate national legislation and administrative requirements

## Reference implementation

This repository contains a **reference implementation** for SDEP implementations (CA, STR, STA, LSA, LMA, AMA) across EU Member States.

The implementation is provided as **guidance only** and can serve as a **blueprint** for national implementations.

The implementation may differ between EU Member States.

## Production (PRD)

The reference implementation is deployed in production (**PRD**) in the Netherlands as **SDEP-NL**

- https://sdep.gov.nl/api/docs.

The production environment (PRD):

- Enables competent authorities (CA) and short-term rental platforms (STR) in the Netherlands to exchange regulated-area, listing (random check) and rental-activity data in accordance with EU legislation
- Includes the **EU-harmonized** short-term rental component (STR)
- Includes the **SDEP-NL-specific** components (CA, STA, ...)

> **Disclaimer (PRD)**: For production use in your own country, always contact your **national SDEP representative** regarding national deployment and operational responsibilities.

For onboarding, see [Getting started in PRD](./docs/GET_STARTED_PRD.md).

## Pre-production testing (PRE)

To facilitate end-to-end testing with integration partners, the reference implementation is also deployed in a dedicated pre-production environment (**PRE**) in the Netherlands within SDEP-NL

- https://pre-sdep.minvro.nl/api/docs.

The pre-production environment (PRE):

- Enables integration partners to test integrations with the **EU-harmonized** short-term rental (STR) component before connecting to production systems
- Also provides testing access to the **SDEP-NL-specific** competent authority (CA) and statistics authority (STA) components

In the PRE environment:

- Only anonymized data should be used
- A daily cleanup takes place to remove any residual test or production-like data

For **onboarding**, see: [Getting started in PRE](./docs/GET_STARTED_PRE.md).

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

In Swagger UI, use **Authorize** to activate either of the following **client authentication methods** (both fall under the same **Client Credentials flow**, see also [Authentication and authorization](./docs/SECURITY.md#authentication-and-authorization)):

- **Client ID & secret** ("client secret auth")

  - This is the default for testing (easier to use)
  - It uses **client-id & secret** to acquire a `Bearer` token, that is used in turn to invoke the other (authenticated) endpoints
  - See [machine-clients.yaml](./keycloak/machine-clients.yaml) for credentials & roles
  - Credentials for all roles are present, so you can replay all end-to-end scenarios (CA, STR, STA, LSA, LMA, AMA)

- **Client-signed JWT** ("client signed JWT auth")

  - This provides a more secure way to test production behaviour
  - It uses **client-signed JWT** to acquire a `Bearer` token, that is used in turn to invoke the other (authenticated) endpoints
  - It requires an additional private/public keypair to generate the client-signed JWT
  - Credentials for all roles are explained in the guidance, so you can test how client-signed JWT authentication works for your role (CA, STR, STA, LSA, LMA, AMA)
  - It also requires you to disable client-secret authentication in your local `.env.extra` (consider a `make backend-restart` to effectuate):
    ```bash
    CLIENT_SECRET_AUTH_ENABLED=false
    ```
  - See [Client-signed JWT authentication](./docs/GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance

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

### Tests (unit)

Backend:

```
cd backend
make test
```

---

### Tests (fullstack, integration)

Fullstack:

```
# Invoke from top-level
make test-full
```

The tests cover the cases as described in the [integration test documentation](./docs/INTEGRATION_TESTS.md).

- Tests are executed against the complete Dockerized stack
- Test suites run sequentially, in the order of `tests/suites.txt` - each exercising the live API over HTTP (Python `httpx`)
- Test data uses the `sdep-test-*` naming convention; this data is automatically detected and removed after each test run (`postgres/clean-testrun.sql`)
- Test isolation is enforced by comparing table row counts before and after execution (PRE/POST); any discrepancy causes the build to fail
- A consolidated summary report presents per-suite and overall totals (executed/passed/failed/skipped) and exits with a non-zero status if any test fails
  - A skipped test (no sample data, no credentials) does not fail the run, but is shown with ⚠️

> Fullstack tests can be reused in Test or Production environments (contact team SDEP-NL for more info).

---

### Tests (migrations)

Alembic migrations are verified separately against PostgreSQL:

```
make test-migrations
```

- Applies all migrations to an empty database (`make -C backend upgrade`)
- Verifies that the models and the database agree: `alembic check` for tables, columns, indexes and unique constraints, `backend/scripts/check_db_matches_models.py` for the CHECK constraints and partial-index predicates, which Alembic does not compare
- Verifies that the check constraints reject bad rows
- Runs without the full stack, so it is also usable as a CI/CD pipeline gate

---

### Tests (performance)

Locust-based load testing for the bulk activity endpoint (`POST /str/activities/bulk`).

```
make test-perf
```

For full configuration options and usage examples, see [Performance tests](./docs/PERFORMANCE_TESTS.md).

---

### Tests (security)

---

**Malware scan (ClamAV)**

Scan uploaded files for malware: `make test-malware`

- Connects directly to the ClamAV container (not the backend API)
- Runs standalone, so it can be used as a CI/CD security gate without starting the full stack

---

**Vulnerability scan (Trivy)**

Scan the backend image for common vulnerabilities and exposures (CVEs): `make test-cve`

This command:

- Rebuilds the backend image from scratch (`--pull --no-cache`) to ensure the latest Debian security updates are included. Cached layers may otherwise retain vulnerabilities already fixed upstream
- Scans the image with Trivy via the `run-trivy-scan` Compose service
- Compares results against `docs/CVE_EXPLAINS.md` and fails if:
  - New CVEs are found that are not allowlisted
  - Allowlisted CVEs are no longer present and should be removed
  - An allowlisted CVE names a package that differs from Trivy's report
  - An allowlisted CVE is filed under a severity that differs from Trivy's report
  - A CVE appears in more than one allowlist row

The scan uses a temporary image tag and does not affect the image used by `make up`.

> **Note:** `docs/CVE_EXPLAINS.md` is intentionally not committed. Each EU member state implementing an SDEP is responsible for maintaining its own CVE allowlist and remediation process within its CI/CD pipeline.

---

**Keeping images up to date**

Security updates are installed via `apt-get upgrade` during the Docker build, so they are only applied when the relevant layer is rebuilt.

- `make up` reuses Docker's build cache for faster local development and therefore does **not** guarantee the latest security patches
- CI/CD should always perform a clean rebuild (e.g. `--pull --no-cache`) before publishing or deploying images
- `make test-cve` already performs such a clean rebuild, ensuring the scan runs against a fully up-to-date image

To refresh your local backend image manually: `make test-cve` or `docker compose build --pull --no-cache backend`.

---

### Tests (all)

Test all in one go (fullstack + migrations + malware + performance):

```
make test
```

Same, keeping the generated test data afterwards (not idempotent, for inspection):

```
make test-keep
```

---

### All

All in one go:

```
make all
```

Definition of Done (every automated check, one status line per step, full logs in `tmp/dod/`):

```
make dod
```

The gate stops at the first failing step. After the fix, continue from that step: the cheap steps (docs checks, API snapshots, Markdown) rerun, the stack-bound suites that already passed are skipped. It refuses when `backend/` changed since the failure, because the backend test and image scan are then stale.

```
make dod-continue
```

## Design

### Style guide

Lint:

```
make md-lint
```

---

Format:

```
make md-format
```

The applied style is as follows (config and custom rules in `docs/markdown-tooling/`):

- Level 1 headings as `<h1>`, so the title stays out of the table of contents
- Max heading depth 3 (`###`); deeper levels become a `---` line plus bold text
- A `---` line before every `###`, except directly after a `##`
- Headings go in **"Sentence case"**, as in the GitHub, Google and Microsoft style guides:
  - Only the first word, the first word after a colon, acronyms and names keep a capital (Competent authority (CA), Swagger UI, ...)
  - Names that must keep their capital go in the `keep` list of `.markdownlint-cli2.jsonc`
- Table alignment,
- `-` list markers (iso. `*`)
- Plain hyphens (no en or em dash)
- Rightmost `# ...` alignment in directory trees

---

Validate links, every relative Markdown link and heading anchor:

```
make md-validate-links
```

---

Language is Oxford English (en-GB-oxendict):

- Prose gets British spelling
- Code names like authorization stay the same as in libraries (`.codespellrc`)

```
make spell-check
```

---

### Definitions

- [Definitions](./docs/DEFINITIONS.md)

---

### Functional

- [Architecture](./docs/ARCHITECTURE_FUNC.md)
- [Host](./docs/HOST_FUNC.md)
- [Area](./docs/AREA_FUNC.md)
- [Listing](./docs/LISTING_FUNC.md)
- [Activity](./docs/ACTIVITY_FUNC.md)

---

### Technical

- [Architecture](./docs/ARCHITECTURE_TECH.md)
- [Host](./docs/HOST_TECH.md)
- [Area](./docs/AREA_TECH.md)
- [Listing](./docs/LISTING_TECH.md)
- [Activity](./docs/ACTIVITY_TECH.md)

---

- [Internal data model](./docs/DATAMODEL_TECH.md)
- [API](./docs/API_TECH.md)
- [API version diff](./docs/API_DIFF_TECH.md)
- [Database dialects](./docs/DATABASE_DIALECTS.md)
- [Development workflow](./docs/DEVELOPMENT.md)

---

### Security

- [Security](./docs/SECURITY.md)

## Getting started

- [Development](#development)
- [Pre-production](./docs/GET_STARTED_PRE.md)
- [Production](./docs/GET_STARTED_PRD.md)
- [Client-signed JWT authentication](./docs/GET_STARTED_CLIENT_SIGNED_JWT.md)

## Known issues

- Multiple CAs can use the same areaId, but platforms act on areaId solely ([#95](https://github.com/SEMICeu/sdep/issues/95))

## Process

- [Way of working](./docs/WOW.md)

## Foundation

This repository builds upon the original foundational work provided by the **Short-Term Rental Application Profile and Prototype (STR-AP)** project:

https://github.com/SEMICeu/STR-AP
