# Changelog

*No impact on the API contract, unless explicitly specified otherwise.*

# 1.3.2

- Fixed bulk activity POST returning HTTP 500 (`MultipleResultsFound`) when duplicate current owner rows existed
- Implemented OAuth 2.0 JWT Client Authentication (RFC 7523), alongside the already implemented OAuth 2.0 Client Credentials Grant (RFC 6749).
  - **OAuth 2.0 JWT Client Authentication** (a.k.a. **client-signed JWT**): is most secure and is the only option supported in SDEP-NL Production (PRD). Supports interactive testing in Swagger UI by first obtaining a bearer token at the `/token` endpoint
  - **OAuth 2.0 Client Credentials Grant** (a.k.a. **client credentials flow)**: is less secure and remains to be supported in SDEP-NL Pre-Production (PRE). Supports interactive testing in Swagger UI by directly authorizing via client id & secret (under the hood, Swagger obtains the bearer token via the `/token` endpoint)
  - Updated the getting started guides (PRE, PRD) accordingly

# 1.3.1

- Improved the performance-test tooling and Makefile test targets
  - Renamed `PERF_YES` to `PERF_AUTO_CONFIRM`, hardened perf-test cleanup to surface real errors and fail on cleanup failure
  - Consolidated the per-table count targets into a single `postgres-count` and added a `test-keep` target
- Include `UNKNOWN` severity CVE's in trivy scan
- Activity filters now use UTC dates
- Rewrote integration tests in python for better portability

# 1.3.0

- Added a read-only Reporting (REP) `v1` API for statistics and reporting offices
  - Gated by a new `sdep_rep` role
  - Featuring endpoints for `GET /api/rep/v1/activities` and `GET /api/rep/v1/activities/count`
  - Returns all current activities across every competent authority and platform
  - Returns at most 1000 records per request (`limit` defaults to 1000, the maximum); use `offset` together with the count endpoint to page through larger result sets.
  - Impact on API contract: new REP `/v1` endpoints; existing APIs unchanged.
- Remediated additional discovered CVEs by raising transitive-dependency security floors
  - Including `cryptography>=48.0.1` (CVE-2026-45447, an OpenSSL heap use-after-free in `PKCS7_verify`, unreachable in SDEP and pinned as defense in depth)
  - Reworked the `constraint-dependencies` from exact `==` pins to `>=` floors, conform dependency pinning policy
- Cleaned up internal code
  - Unified the CA and STR sub-application setup into a shared `create_domain_app` factory
  - Generalized the activity read and count layers to support the unscoped reporting reads
  - Removed dead test code

# 1.2.0

- Added filtering support to the CA activities endpoint in `v2` API (date range, platform, and area) ([#71](https://github.com/SEMICeu/sdep/issues/71)). Impact on API contract: new CA `/v2` endpoints; CA `/v1` unchanged.
- Added database-level constraints backing the existing application-level constraints (defense in depth)
- Added markdown linting and formatting

# 1.1.5

- Fixed Keycloak/JWKS infrastructure errors being misclassified as HTTP 401; they now return HTTP 503
- Fixed /api/auth/v1/token returning HTTP 500 instead of HTTP 503 when Keycloak responds with a malformed body

# 1.1.4

- Pinned the transitive Starlette dependency to fix CVE-2026-48710 (BadHost)

# 1.1.3

- Added a "make trivy" to run trivy on local machine
- Improved the make test targets to ensure/start fullstack, and to avoid a needless backed recreate
- Improved test portability
- Updated transitive dependency (idna) to fix CVE-2026-45409
- Updated documentation to reflect code changes

# 1.1.2

- Fixed the OAuth client ID validation regex to reject backslashes
- Documentation updates
- Added a script to generate EICAR files automatically, can be used to verify malware scanning

# 1.1.1

- Patch: periods and underscores were rejected erroneously, this is now fixed

# 1.0.1

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

- Added versioning policy to the [API documentation](./docs/API.md)
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
- Updated `DATAMODEL.md`, `SECURITY.md`, `API.md`, and `README.md`
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
- Improved audit logging (_write_audit_record now uses exc_info=True for full tracebacks instead of stringifying the exception)
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

- Added `Area.regulation` with values `listing, address, all` (conform Regulation, Article 13); default is all ([#5](https://github.com/SEMICeu/sdep/issues/5))
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
- Extended unique constraints on Area  (because CAs may use the same business identifiers)
- Extended unique constraints on Activity (because STRs may use the same business identifiers)
- Added list and count endpoints for CA (`GET /ca/areas`, `GET /ca/areas/count`, `GET /ca/activities`, `GET /ca/activities/count`)
- Added list and count endpoints for STR (`GET /str/areas`, `GET /str/areas/count`, `GET /str/areas/{areaId}`, `GET /str/activities`, `GET /str/activities/count`)
- Changed default sorting for GET into `createdAt`, descending

## 251228

- Evolved version of original prototype
