# Changelog

## 260409

- Added Area.regulation (listing, address, all) conform Regulation, Article 13 >> default is all
- Improved functional ID validation >> accepts uppercase alphanumeric IDs too
- Improved documentation for performance test data
- Improved some makefile test targets
- Improved the version-independent endpoint for /api/docs
- Made local Postgres port configurable per developer

## 260401

- Harmonized Address to EU/INSPIRE >> impacts API >> see [migration guide](./docs/MIGRATION_ADDRESS_INSPIRE.md)

## 260330

- Removed "proposed" from the bulk activity endpoint >> final (no impact on API)
- Added config got application connection pool (same defaults as before, no impact on API)
- Improved performance tests
- Added all validation errors in bulk activity endpoint response (instead of only the first error)
- Fixed Amsterdam shapefile

## 260325

- Added a bulk activity endpoint `POST /str/activities/bulk` (up to 1000 items/batch, proposed)

## 260323

- Trimmed-down the audit log (technical management only)

## 260320

- Updated WoW with issue labels
- Added a warning about using only anonymized data in the pre-production (PRE) environment

## 260319

- Implemented audit log (incl. retention)

## 260304

- Implemented validation for ISO 3166-1 alpha-3 country code

## 260303

- Improved Quick start (local workstation) >> keycloak config

## 260227

- Reverted the list and count endpoints for STR to retrieve their own data (`GET /str/activities`, `GET /str/activities/count`) >> discuss

## 260225

- Improved the OpenAPI examples for POST/GET activities

## 260224

- Unified exception handling and HTTP status codes
- Added `competentAuthorityId` and `competentAuthorityName` to (who own the `areaId` in) the activity responses

## 260220

- Removed redundant submitter id/name from POST response
- Added GET area by ID endpoint for CA (`GET /ca/areas/{areaId}`)
- Made `Activity.url` mandatory

## 260218

- Added DELETE area endpoint for CA (`DELETE /ca/areas/{areaId}`)

## 260217

- Improved (consistency) in endpoint documentation and payload ordering
- Use standard MIME type (application/zip) for area shapefile download endpoint

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
