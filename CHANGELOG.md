# Changelog

## 260220

- Removed redundant submitter id/name from POST response
- Added GET area by ID endpoint for CA (`GET /ca/areas/{areaId}`)

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
