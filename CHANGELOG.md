# Changelog

## 260507

- Improved API doc (corrected a typo)
- Hardened pagination impl and some tests
- Improved security headers (enabled CORP, fixed CSP, consistently enabled HSTS)
- Improved [security documentation](./docs/SECURTITY.md)

*No API v1 impact*

## 260506

- Improved API doc

*No API v1 impact*

## 260505

- Eliminated dict-mapping boilerplate (services now return ORM objects directly; routers use model_validate for serialization)
- Simplified schema-ORM binding
- Added ActivityBulkCreate subclass (to avoid manual dict assembly)
- Improved audit logging (_write_audit_record now uses exc_info=True for full tracebacks instead of stringifying the exception)
- Increased test coverage
- Bumped Pyright to >=1.1.409
- Enforced code coverage to 100% (TYPE_CHECKING blocks excluded since they never run at runtime; guard: --cov-fail-under=100)
- Added a "make check" prerequisite to "make test" targets

*No API v1 impact*

## 260424 - API v1 freeze

- Froze the API into `/v1`
- Moved from a single versioned mount (`/api/v0`) to independent per-domain versioning (`/api/auth/v1`, `/api/ca/v1`, `/api/str/v1`)
- Health and ping are unversioned at `/api/health` and `/api/ping`
- PDF exports included
- No schema changes

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
- Improved Dockerfile to harden outage of `install.sh` package from https://astral.sh/uv
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

- Harmonized `Address` to EU/INSPIRE >> impacts API >> see [migration guide](./docs/MIGRATION_ADDRESS_INSPIRE.md) ([#31](https://github.com/SEMICeu/sdep/issues/31))

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
