<h1>Changelog</h1>

*No impact on the API contract, unless explicitly specified otherwise.*

*See also the [API design](./docs/API_TECH.md) and the [version differences](./docs/API_DIFF_TECH.md).*

<h1>1.7.0</h1>

- Introduced random checks/flagged listings (v2, alpha)
  - **No impact on EU-harmonized v1**
  - Yet `alpha` to materialize the concept; deployed in pre-production (PRE), but [not yet in production (PRD)](./docs/API_TECH.md#versioning)
  - Based on [functional](./docs/LISTING_FUNC.md) and [technical design](./docs/LISTING_TECH.md)
- Added activity monitoring authority (AMA, v1)
  - **No impact on EU-harmonized v1** (this change is country-specific)
- Renamed reporting and statistics (REP, v1) to statistics authority (STA, v1)
  - **No impact on EU-harmonized v1** (this change is country-specific)
- Fixed technical issues
  - **No impact on EU-harmonized v1**
- Improved documentation

---

**Impact**

---

v1:

| Scope             | Code  | Version | Meta     | Delta                 | Notes                                               |
| ----------------- | ----- | ------- | -------- | --------------------- | --------------------------------------------------- |
| **EU-harmonized** | `STR` | `v1`    | `stable` | **No impact**         |                                                     |
| Country-specific  | `CA`  | `v1`    | `stable` | Narrowed              | GET areas & activities: max 1000 iso. unlimited [1] |
| Country-specific  | `CA`  | `v1`    | `stable` | Widened               | GET activities: additional query filters [1]        |
| Country-specific  | `AMA` | `v1`    | `stable` | Alpha > beta > stable | Added activity monitoring authority                 |
| Country-specific  | `STA` | `v1`    | `stable` | Alpha > beta > stable | Added statistics authority                          |

[1] Backported from CA/v2 to CA/v1, because CA/v2 is now `alpha` and (for now) not yet in production anymore (to avoid alpha data pollution)

---

v2:

| Scope             | Code  | Version | Meta    | Delta            | Notes                                                                  |
| ----------------- | ----- | ------- | ------- | ---------------- | ---------------------------------------------------------------------- |
| **EU-harmonized** | `STR` | `v2`    | `alpha` | **Beta > alpha** | Was introduced in 1.6.0 as `beta`, but is re-introduced as `alpha` [2] |
| **EU-harmonized** | `STR` | `v2`    | `alpha` | **Narrowed**     | GET areas: max 1000 iso. unlimited                                     |
| **EU-harmonized** | `STR` | `v2`    | `alpha` | **Narrowed**     | POST activities: validate temporal on UTC                              |
| **EU-harmonized** | `STR` | `v2`    | `alpha` | **Narrowed**     | POST activities: validate area on regulation (`activity` or `all`)     |
| **EU-harmonized** | `STR` | `v2`    | `alpha` | **Widened**      | POST activities: `url` to 2048 characters                              |
| **EU-harmonized** | `STR` | `v2`    | `alpha` | **Widened**      | POST activities: `fullAddress` to 328 characters                       |
| Country-specific  | `CA`  | `v2`    | `alpha` | Beta > alpha     | Was introduced in 1.2.0 as `beta`, but is re-introduced as `alpha` [2] |
| Country-specific  | `CA`  | `v2`    | `alpha` | Narrowed         | GET activities: `url` to 2048 characters                               |
| Country-specific  | `CA`  | `v2`    | `alpha` | Narrowed         | GET activities: `fullAddress` to 328 characters                        |
| Country-specific  | `LSA` | `v2`    | `alpha` | New              | Added listing screening authority                                      |
| Country-specific  | `LMA` | `v2`    | `alpha` | New              | Added listing monitoring authority                                     |
| Country-specific  | `STA` | `v2`    | `alpha` | New              | Added listings to statistics authority                                 |

[2] Because v2 now focuses on listings (random checks), and is work in progress (WIP).

---

*Pending technical working group (TWG): consider to [backport some fixes from `v2` to `v1`](https://github.com/SEMICeu/sdep/issues/94).*

---

**Details**

- Introduced random checks/flagged listings
  - Extended the [datamodel](./docs/DATAMODEL_TECH.md) with listing
  - Added keycloak role LSA (`sdep_lsa`, listing screener authority)
  - Added keycloak role LMA (`sdep_lma`, listing monitoring authority)
  - Implemented endpoints + backend
- Enhanced the API doc and example for activity regulation
  - In STR `v2`, the activity item is a reference to `Activity.RequestV2`, and the example shows a `regulation_error`
  - In testdata, Amstelveen and Bergen are now regulated for listing only (to support the STR `v2` `regulation_error` example)
- Backported from CA `v2` to CA `v1`
  - The four optional activity filters (`createdAtFrom`, `createdAtTo`, `platformId`, `areaId`) on `GET /activities` and `GET /activities/count`
  - `GET /areas` and `GET /activities` return at most 1000 records per call (`limit` defaults to 1000, the maximum)
- Kept the STR `v1` input limits for `url` (128) and `fullAddress` (318); STR `v2` accepts 2048 and 328 characters
  - Database migration `007` widens the `url` and `fullAddress` columns to 2048 and 328
- Updated [API versioning](./docs/API_TECH.md#design) (alpha, beta, stable, deprecated)
- Updated the API docs
  - Added `info.contact` in the OpenAPI document and the `API-Version` response header
  - Added `info.version` as application version in the OpenAPI document (`1.7.0` instead of `PRD-1.7.0`)
  - Domains are now grouped by version (authentication, activities, listings); within each version by scope; and within scope sorted alphabetically
  - Every row shows the acronym spelled out (right-aligned), with the names conforming to [Definitions](./docs/DEFINITIONS.md)
  - Documented the field maximums of the activity responses (e.g. `url` 2048, `fullAddress` 328, `registrationNumber` 32), the database already enforces the same limits
- Validated and [documented](./docs/API_TECH.md#nlgov-rest-api-design-rules) compliance with the [NLgov REST API Design Rules](https://gitdocumentatie.logius.nl/publicatie/api/adr/2.2.0/) and fixed some gaps (generic)
  - `/core/no-trailing-slash`: a trailing slash returns 404 instead of a 307 redirect (but kept `v1` untouched)
  - `/core/version-header`: every response carries `API-Version: <major.minor.patch>` (the release version; the contract major stays in the path)
  - `/core/semver`: OpenAPI `info.version` is the release version (`1.7.0` instead of `PRD-1.7.0`); the environment moved to its own landing-page badge; the local default is `0.0.0-dev`
  - `/core/transition-period`: a deprecated version stays at least six months after the `Sunset` announcement (at this stage: proposal, requires discussion in technical working group)
  - `/core/doc-openapi-contact`: every OpenAPI document publishes `info.contact` (name, url, email), configurable per deployment (`API_CONTACT_*`), also shown in the landing-page footer
  - `/core/transport/cors`: the no-cross-origin policy is stated explicitly in [Security](./docs/SECURITY.md#security-headers)
- Added keycloak role AMA (activity monitoring authority, `sdep_ama`)
- Renamed keycloak role REP (`sdep_rep`, reporting) to STA (`sdep_sta`, statistics authority)
- Upgraded the backend from Python 3.13 to 3.14
  - Upgraded the packages that had no Python 3.14 wheels in the lock: `pydantic` (2.13), `pydantic-core`, `asyncpg`, `uvloop` and `httptools`
  - Disabled Ruff rules TC001 and TC002 project-wide because Python 3.14’s lazy type hints conflict with frameworks that still inspect annotations at runtime.
- Refreshed all backend dependencies (`uv lock --upgrade`, around 53 packages, among which `fastapi` 0.141, `sqlalchemy` 2.1, `pytest` 9, `ruff` 0.16 and `reportlab` 5)
  - Adapted the `Select` type hints to SQLAlchemy 2.1
  - Switched the `str, Enum` classes to `StrEnum`, as ruff 0.16 asks
  - Made the write-session test walk included routers again, since FastAPI 0.141 no longer copies their routes into `app.routes`
- Replaced the synchronous database driver `psycopg2-binary` with `psycopg[binary]` (v3), the default of SQLAlchemy 2.1, used by Alembic
  - Removed `libpq` from the backend image, since `psycopg[binary]` bundles its own; this dropped 9 OS-level CVEs (LDAP, Kerberos) from the allowlist
- Fixed endpoints that returned a 2xx before the real commit
- Derive the audit skip list (`SKIP_PATHS`) and the security headers (no-cache prefixes, Swagger UI docs paths) now straight away from the domain registry (`API_DOMAINS`)
  - So a new API version needs no edit in `app/security/audit.py` or `app/security/headers.py`
- Locked the backend type completeness check (`ty`) as a development dependency and run it via `uv run`, alongside `ruff` and `pyright`
  - Ensured the same version is used locally and in CI
  - Eliminated package fetching at runtime
- Remediated two dependency CVEs and refreshed the CVE allowlist (internal use only)
  - Raised `anyio` to `>=4.14.2` (CVE-2026-63374, host name check with IDNA 2003 in `connect_tcp()`; CVE-2026-64847, blocked process-pool workers)
- Added a `make dod` (Definition of Done) target
- Split documentation into functional (`*_FUNC.md`) and technical (`*_TECH.md`) parts

<h1>1.6.0</h1>

- Added STR `v2` (beta, EU GitHub issues [#75](https://github.com/SEMICeu/sdep/issues/75), [#80](https://github.com/SEMICeu/sdep/issues/80), [#81](https://github.com/SEMICeu/sdep/issues/81), [#83](https://github.com/SEMICeu/sdep/issues/83), [#84](https://github.com/SEMICeu/sdep/issues/84))
  - Activity timestamps must be UTC (offset `Z` or `+00:00`); other offsets (e.g. CET `+01:00`), no offset and date-only values are rejected
  - Activities are rejected for areas that are regulated for listing only, per item (`regulation_error`)
  - `GET /areas` returns at most 1000 areas per call (`limit` defaults to 1000, the maximum)
  - Impact on API contract: new STR `/v2` endpoints; STR `v1` behavior unchanged
- Widened `url` to 2048 and `fullAddress` to 328 characters
  - No impact on STR `v1` (POST request maximums are relaxed, contract widening, backward compatible)
  - Impact on CA and STA `v1`: responses may carry longer values, so clients that size their own storage from the documented maximums should widen it
  - *In 1.7.0 moved back to /v2: requires additional impact analysis and agreement in TWG first*
- Enhanced CA `v2`:
  - `GET /areas` and `GET /activities` return at most 1000 records per call (`limit` defaults to 1000, the maximum)
  - *In 1.7.0 backported to /v1: because of v2 became alpha, not yet be in production*
- Downgraded STA `v1` from `beta` to `alpha`
  - Awaiting feedback from the reporting/statistics offices
- Improved local development:
  - `make up` now reloads on `app/` only, so the watcher no longer includes `.venv` (so to avoid possible `OS file watch limit reached`)
- Fixed a crash in STR `v1` bulk submissions when one timestamp has a timezone and the other has not
  - Example: `"startDatetime": "2025-06-01"` (a date only, no timezone) together with `"endDatetime": "2025-06-07T11:00:00+02:00"` (with timezone)
  - Python cannot compare such a pair, so the start-before-end check crashed and the whole batch got a 500 instead of a per-item result
  - Now a timestamp without timezone is read as UTC before any check, which is how the database already stored it; nothing changes for platforms that send a timezone

<h1>1.5.0</h1>

- Removed the redundant filter prefix in the CA v2 and STA v1 (impacts the beta contract for both, no impact on STR v1)
- Test CA v1 and v2 (beta) instead of only v1
- Fine-tuned the functional design proposal for [listing regulation](./docs/LISTING_FUNC.md) aka. random checks

<h1>1.4.3</h1>

- Split EU-harmonized and country-specific on the `/apis/docs` (main) page
- Hardened the local keycloak startup for development purposes
- Fine-tuned the functional design proposal for [listing regulation](./docs/LISTING_FUNC.md) aka. random checks

<h1>1.4.2</h1>

- Restructured the [functional design](./README.md#functional)
- Renewed the functional design proposal for [listing regulation](./docs/LISTING_FUNC.md) aka. random checks
- Added [API version diff](./docs/API_DIFF_TECH.md), showing what changed between two API versions, generated from the API itself so it cannot go stale
- Added a link to that version comparison on the API documentation page
- Each API version now says in its own documentation whether it supersedes, or is superseded by, another version
- Added an interactive documentation page for the ping endpoint, so a token can be entered, and the endpoint tried out
- Grouped ping and health together on the API documentation page, and put the environment and OpenAPI version at the top
- Split the API domains on the API documentation page into EU-harmonized (Auth, STR) and country-specific (CA, STA)
- Hardened the local Keycloak startup
  - A pre-built optimized image with local cache replaces the stock image
  - Cutting startup from minutes to seconds
  - Removing cluster discovery timeouts on stale rows
  - The wait script now fails fast when the container exits
- Removed an unused route in every API that was shadowed by the framework's own
- Moved the API endpoint overview from the architecture document into the API document
- Cleaned up duplicated version labels, a leftover test file and inaccurate makefile messages

<h1>1.4.1</h1>

- Replaced the contact address on the API docs landing page with the functional mailbox `nationaalcoordinatorsdep@minbzk.nl`
- Split the CVE check into separate steps

<h1>1.4.0</h1>

- Added the optional `areaName` field to activity responses
  - Populated `areaName` from the related area for CA v1 and v2 activity lists, STA v1 activity lists, and successful STR v1 bulk response items
  - No breaking API changes: `areaName` is an optional response field, so existing clients remain compatible
- Corrected the integration test documentation and HSTS check
  - Clarified that the application also sets the `Strict-Transport-Security` header itself rather than delegating it to the reverse proxy
- Corrected the description of the OAuth 2.0 Client Credentials grant across documentation and code comments
  - Clarified that client ID/secret and client-signed JWT are not separate OAuth flows;
  - both use the OAuth 2.0 Client Credentials grant and differ only in the client authentication method (`client_secret_post` / `client_secret_basic` versus `private_key_jwt`)
  - Updated the getting-started documentation for **PRE** and **PRD** accordingly
- Renamed `CLIENT_CREDENTIALS_FLOW_ENABLED` to `CLIENT_SECRET_AUTH_ENABLED`
  - Clarified that optional client-secret authentication and always-enabled client-signed JWT authentication are both authentication methods within the Client Credentials flow
  - No impact on the API contract
- Improved Makefile test targets and preserving the optional "keep testdata" behavior
- Made `tests/test_auth_client_jwt.py` reusable against deployed environments
- Remediated two dependency CVEs and refreshed the CVE allowlist
  - Raised `cryptography` to `>=50.0.0` (CVE-2026-69247, a Bleichenbacher oracle in the PKCS7 decrypt helpers) and `python-dotenv` to `>=1.2.2` (CVE-2026-28684, symlink following in `set_key()` / `unset_key()`); SDEP reaches neither code path, so both floors are defense in depth
  - Documented 17 newly reported OS-level CVEs and removed one stale entry
- Improved the CVE scan (1/3)
  - Nine CVE allowlist rows named a package the scanner does not report for that CVE;
  - for seven of them the recorded justification did not apply to the affected component at all, so the risk acceptance was never valid
  - CVE-2026-5435, CVE-2026-6238 and CVE-2026-28684 were accepted on the grounds that "SDEP does not use GnuTLS", but are glibc and `python-dotenv` flaws
  - CVE-2026-27171 and CVE-2026-5704 were accepted as systemd flaws, but are zlib and tar flaws
  - CVE-2026-3184 and CVE-2026-27456 were accepted as libgcrypt and systemd flaws, but are util-linux flaws
  - CVE-2026-5450 and CVE-2026-5928 named the source package `glibc` rather than the reported binary packages `libc-bin` / `libc6`;
  - the justification held, but the row could not be matched against the scan
  - All nine have been re-justified against the component the scanner actually reports;
  - CVE-2026-28684 turned out to be fixable once correctly attributed and was remediated by the `python-dotenv` bump above rather than re-accepted
  - Separately, 11 entries were re-filed under the severity the scanner reports, and duplicate rows for four `perl-base` CVEs (each listed under three headings) were collapsed
- Improved the CVE scan (2/3)
  - `scripts/run-trivy-scan.sh` now fails when an allowlist row names a package Trivy does not report for that CVE, sits under a heading that does not match the reported severity, or repeats a CVE
  - Previously only CVE ids were compared, which is why the wrong-package and wrong-severity entries above went undetected
  - The scan report is now rendered by Trivy itself instead of being scraped out of the results JSON
- Improved the CVE scan (3/3)
  - Trivy version has been pinned

<h1>1.3.2</h1>

- Fixed bulk activity POST returning HTTP 500 (`MultipleResultsFound`) when duplicate current owner rows existed
- Implemented OAuth 2.0 JWT Client Authentication (RFC 7523), alongside the already implemented OAuth 2.0 Client Credentials Grant (RFC 6749).
  - **OAuth 2.0 JWT Client Authentication** (a.k.a. **client-signed JWT**): is most secure and is the only option supported in SDEP-NL Production (PRD).
  - Supports interactive testing in Swagger UI by first obtaining a bearer token at the `/token` endpoint
  - **OAuth 2.0 Client Credentials Grant** (a.k.a. **client credentials flow)**: is less secure and remains to be supported in SDEP-NL Pre-Production (PRE).
  - Supports interactive testing in Swagger UI by directly authorizing via client ID & secret (under the hood, Swagger obtains the bearer token via the `/token` endpoint)
- Updated the getting started guides (PRE, PRD) accordingly

<h1>1.3.1</h1>

- Improved the performance-test tooling and Makefile test targets
  - Renamed `PERF_YES` to `PERF_AUTO_CONFIRM`, hardened perf-test cleanup to surface real errors and fail on cleanup failure
  - Consolidated the per-table count targets into a single `postgres-count` and added a `test-keep` target
- Include `UNKNOWN` severity CVE's in trivy scan
- Activity filters now use UTC dates
- Rewrote integration tests in python for better portability

<h1>1.3.0</h1>

- Added a read-only Reporting (STA) `v1` API for statistics and reporting offices
  - Gated by a new `sdep_sta` role
  - Featuring endpoints for `GET /api/sta/v1/activities` and `GET /api/sta/v1/activities/count`
  - Returns all current activities across every competent authority and platform
  - Returns at most 1000 records per request (`limit` defaults to 1000, the maximum); use `offset` together with the count endpoint to page through larger result sets.
  - Impact on API contract: new STA `/v1` endpoints; existing APIs unchanged.
- Remediated additional discovered CVEs by raising transitive-dependency security floors
  - Including `cryptography>=48.0.1` (CVE-2026-45447, an OpenSSL heap use-after-free in `PKCS7_verify`, unreachable in SDEP and pinned as defense in depth)
  - Reworked the `constraint-dependencies` from exact `==` pins to `>=` floors, conform dependency pinning policy
- Cleaned up internal code
  - Unified the CA and STR sub-application setup into a shared `create_domain_app` factory
  - Generalized the activity read and count layers to support the unscoped reporting reads
  - Removed dead test code

<h1>1.2.0</h1>

- Added filtering support to the CA activities endpoint in `v2` API (date range, platform, and area) ([#71](https://github.com/SEMICeu/sdep/issues/71)).
  - Impact on API contract: new CA `/v2` endpoints; CA `/v1` unchanged.
- Added database-level constraints backing the existing application-level constraints (defense in depth)
- Added markdown linting and formatting

<h1>1.1.5</h1>

- Fixed Keycloak/JWKS infrastructure errors being misclassified as HTTP 401; they now return HTTP 503
- Fixed /api/auth/v1/token returning HTTP 500 instead of HTTP 503 when Keycloak responds with a malformed body

<h1>1.1.4</h1>

- Pinned the transitive Starlette dependency to fix CVE-2026-48710 (BadHost)

<h1>1.1.3</h1>

- Added a "make trivy" to run trivy on local machine
- Improved the make test targets to ensure/start fullstack, and to avoid a needless backed recreate
- Improved test portability
- Updated transitive dependency (idna) to fix CVE-2026-45409
- Updated documentation to reflect code changes

<h1>1.1.2</h1>

- Fixed the OAuth client ID validation regex to reject backslashes
- Documentation updates
- Added a script to generate EICAR files automatically, can be used to verify malware scanning

<h1>1.1.1</h1>

- Patch: periods and underscores were rejected erroneously, this is now fixed

<h1>1.0.1</h1>

- Fixed a bug where one CA could take over another CA’s areaId
- Improved file upload/download sanitization
- Added JWT signature verification to prevent audit-log role forgery/poisoning
  - Now recording verified role sets for 403 responses only, while preserving protection against forged JWT role data
  - 401 (unauthorized): `roles = NULL`;
  - 403 (forbidden): the verified role set
  - Removed the earlier introduced `REJECTED` / `UNAUTHORIZED` sentinel role values (see 260518)
- Added malware scanning support, including tests
- Removed invalid `speaker=(self)` from `Permissions-Policy`
- Narrowed Basic Auth parser exception handling on `/api/auth/v1/token` (previously a bare `except Exception` could mask unrelated errors)
- Optimized audit middleware by reusing the verified JWT payload from `request.state` instead of re-verifying the token
- Removed the no-op `add_done_callback` on the audit-write background task and replaced it with strong task references (so the task is not garbage-collected mid-flight)
- Refactored intra-batch deduplication in `services/activity_bulk.py` into a clearer two-pass form (build last-index map, then mark superseded items NOK); behavior unchanged
- Removed empty `AuditLogMiddleware.__init__` override
- Implemented fail fast for oversized area uploads (HTTP 413 when `Content-Length` exceeds the configured limit
  - Technically narrows the CA v1 contract, but does not demand for a CA `/v2` yet
- Fixed API exposure to return functional identifiers instead of JWT-based client identifiers for Platform and Competent Authority
  - Ensures private authentication identifiers remain internal
  - Exposes only functional identifiers intended for external API usage
  - Updated the examples in the Swagger docs accordingly. These changes are tracked in `./backend/tests/api/fixtures/openapi_*.json`.
- Added support for periods and underscores in JWT client-ids
- Added some Makefile improvements
- Removed unused code (CRUD hard deletes)
- Extended tests and updated documentation

## 1.0.0

- Added versioning policy to the [API documentation](./docs/API_TECH.md)
- Added a smoke test that runs without test data, making it particularly useful for execution against production environments
- Added postgres utility targets to Makefile

## 260518

- Replaced `python-jose` with `PyJWT`
  - `python-jose` is unmaintained and has a known CVE (CVE-2024-33663) exposing the application to token forgery
- Added JWKS key rotation with 5-minute TTL
  - `@lru_cache` cached keys indefinitely, so rotated or revoked keys in keycloak (backchannel) were never refreshed
- Added pessimistic locking (`SELECT ... FOR UPDATE`) for single-entity and bulk versioning
  - The read-then-write pattern without locking allowed concurrent requests to create duplicate active records
- Added 10s timeout to httpx Keycloak calls
  - Without a timeout, an unresponsive Keycloak hangs API worker threads indefinitely
- Run Docker container as non-root user
  - A container escape or code execution vulnerability would otherwise grant root-level host access
- Switched `get_own_areas` to read-only DB session
  - The GET endpoint used a write-capable session, acquiring unnecessary locks
- Removed 6 unused dependencies (`passlib`, `bcrypt`, `python-keycloak`, `aiofiles`, `aiohttp`, `jsonschema`)
  - Reduces attack surface and image size
- Converted eager f-string logger calls to deferred `%s`-style formatting
  - f-strings build the message even when the log level is disabled
- Documented rate limiting policy
  - Per client IP, delegated to deployment environment
- Restructured `ARCHITECTURE_TECH.md`
  - Split out `DATABASE_DIALECTS.md` and `DEVELOPMENT.md`
- Updated `DATAMODEL_TECH.md`, `SECURITY.md`, `API_TECH.md`, and `README.md`
- Bumped FastAPI from 0.118.0 to 0.136.1
- Bumped Starlette from 0.48.0 to 1.0.0
  - Consequently, file upload for CA now uses `contentMediaType: application/octet-stream` instead of `format: binary` in the OpenAPI spec
  - CA remains the same at runtime (does not require upgrade to /v2); but generated clients may see a spec diff
  - STR remains untouched
- Restricted area file uploads to `.zip` only ([#73](https://github.com/SEMICeu/sdep/issues/73))
  - Aligns POST behavior with the existing `application/zip`-only GET endpoint
  - Technically narrows the CA v1 contract, but does not require a CA `/v2`: only zipped shapefiles were practically supported already
- Sanitized user-supplied filenames in `Content-Disposition` headers
  - Previously, unsanitized filenames allowed header injection via `"`, `\r`, `\n`
- Hardened audit log role extraction to record roles only for successfully authenticated requests
  - Rejected tokens now log `REJECTED` (401) or `UNAUTHORIZED` (403) instead of attacker-controlled role values
  - Previously, forged JWTs containing fabricated roles could pollute audit records even when the request was rejected

## 260507

- Improved API doc (corrected a typo)
- Hardened pagination impl and some tests
- Improved security headers (enabled CORP, fixed CSP, consistently enabled HSTS)
- Improved [security documentation](./docs/SECURITY.md)

## 260506

- Improved API doc

## 260505

- Eliminated dict-mapping boilerplate (services now return ORM objects directly; routers use model_validate for serialization)
- Simplified schema-ORM binding
- Added ActivityBulkCreate subclass (to avoid manual dict assembly)
- Improved audit logging (\_write_audit_record now uses exc_info=True for full tracebacks instead of stringifying the exception)
- Increased test coverage
- Bumped Pyright to >=1.1.409
- Enforced code coverage to 100% (TYPE_CHECKING blocks excluded since they never run at runtime; guard: --cov-fail-under=100)
- Added a "make check" prerequisite to "make test" targets

## 260424 - API v1 freeze

- Froze the API into `/v1`
- Moved from a single versioned mount (`/api/v0`) to independent per-domain versioning (`/api/auth/v1`, `/api/ca/v1`, `/api/str/v1`)
- Health and ping are unversioned at `/api/health` and `/api/ping`
- PDF exports included
- No schema changes

*Impact on API contract: /v1 is frozen.*

## 260422

- Added PDF export of API (yet draft)

## 260421

- Added `Address.fulladdress` as a fallback for CAs to handle cases where STRs incorrectly split address fields ([#62](https://github.com/SEMICeu/sdep/issues/62))
- Added `Activity.status` (default `finished`) to handle cases where STRs report an activity as `cancelled` afterwards ([#48](https://github.com/SEMICeu/sdep/issues/48))
- Made `Activity.numberOfGuests` and `Activity.countryOfGuests` required, validated that they match, and allowed `N/A` for `Activity.countryOfGuests` ([#45](https://github.com/SEMICeu/sdep/issues/45))
- Improved typing of `ActivityBulkRequest` and extended the docs ([#68](https://github.com/SEMICeu/sdep/issues/68))
- Improved OpenAPI schema titles to qualifier-first dotted form (e.g. `Activity.Request`, `Activity.BulkRequest`, ...)
- Promoted `Address` and `Temporal` composites to the new `Common` qualifier
- Renamed Python classes to match the qualifier-first convention (`BulkActivityRequest` → `ActivityBulkRequest`, `AddressRequest` → `CommonAddressRequest`, etc.)
- Improved Dockerfile to harden outage of `install.sh` package from <https://astral.sh/uv>
- Extended the integration tests (added bulk to the standard "make test", and allow for a "make test-keep")
- Hardened the performance tests

## 260420

- Kept `POST /str/activities/bulk` only, removed the single `POST /str/activities/` ([#59](https://github.com/SEMICeu/sdep/issues/59))
- Unified the `Activity`, `Area`, and `Error` response schemas ([#59](https://github.com/SEMICeu/sdep/issues/59))
- Unified terminology in various descriptions
- Updated examples to latest testdata
- Added `.env.extra.example` to allow customization of the local Postgres port (when testing fullstack)
- Actualized various documentation (docs/)

## 260415

- Improved performance test and (validation) documentation

## 260410

- Refactored internal authentication handling

## 260409

- Added `Area.regulation` with values `listing, activity, all` (conform Regulation, Article 13); default is all ([#5](https://github.com/SEMICeu/sdep/issues/5))
- Improved functional ID validation >> accepts uppercase alphanumeric IDs too ([#51](https://github.com/SEMICeu/sdep/issues/51))
- Improved documentation for performance test data
- Improved some makefile test targets
- Improved the version-independent endpoint for `/api/docs`
- Made local Postgres port configurable per developer

## 260401

- Harmonized `Address` to EU/INSPIRE

*Impact on API contract: see [migration guide](./docs/MIGRATION_ADDRESS_INSPIRE.md) ([#31](https://github.com/SEMICeu/sdep/issues/31))*

## 260330

- Removed "proposed" from the bulk activity endpoint >> final (no impact on API)
- Added config for application connection pool (same defaults as before, no impact on API)
- Improved performance tests
- Added all validation errors in bulk activity endpoint response (instead of only the first error)
- Fixed Amsterdam shapefile

## 260325

- Added a bulk activity endpoint `POST /str/activities/bulk` (up to 1000 items/batch)

## 260323

- Trimmed-down the audit log (technical management only, [#49](https://github.com/SEMICeu/sdep/issues/49))

## 260320

- Updated WoW with issue labels
- Added a warning about using only anonymized data in the pre-production (PRE) environment

## 260319

- Implemented audit log (incl. retention, [#50](https://github.com/SEMICeu/sdep/issues/50))

## 260304

- Implemented validation for ISO 3166-1 alpha-3 country code ([#18](https://github.com/SEMICeu/sdep/issues/18))

## 260303

- Improved Quick start (local workstation) >> keycloak config

## 260227

- Reverted the list and count endpoints for STR to retrieve their own data (`GET /str/activities`, `GET /str/activities/count`, [#41](https://github.com/SEMICeu/sdep/issues/41))

## 260225

- Improved the OpenAPI examples for POST/GET activities

## 260224

- Unified exception handling and HTTP status codes ([#17](https://github.com/SEMICeu/sdep/issues/17))
- Added `Activity.competentAuthorityId` and `Activity.competentAuthorityName` (referencing the owning CA)

## 260220

- Removed redundant submitter id/name from POST response
- Added `GET /ca/areas/{areaId}` endpoint
- Made `Activity.url` required ([#16](https://github.com/SEMICeu/sdep/issues/16))

## 260218

- Added `DELETE /ca/areas/{areaId}` ([#27](https://github.com/SEMICeu/sdep/issues/27))

## 260217

- Improved (consistency) in endpoint documentation and payload ordering
- Use standard MIME type (application/zip) for area shapefile download endpoint ([#32](https://github.com/SEMICeu/sdep/issues/32))

## 260216

- Changed POST endpoints to accept single records only
- Changed POST endpoints to have request/response with the same ordening: additional id/name/createdAt are now moved to the end
- Removed redundant indexes on primary keys
- Added `endedAt` next to `createdAt` (for stacking purposes)
- Extended unique constraints on Area (because CAs may use the same business identifiers)
- Extended unique constraints on Activity (because STRs may use the same business identifiers)
- Added list and count endpoints for CA (`GET /ca/areas`, `GET /ca/areas/count`, `GET /ca/activities`, `GET /ca/activities/count`)
- Added list and count endpoints for STR (`GET /str/areas`, `GET /str/areas/count`, `GET /str/areas/{areaId}`, `GET /str/activities`, `GET /str/activities/count`)
- Changed default sorting for GET into `createdAt`, descending

## 251228

- Evolved version of original prototype
