# Changelog

## 260220

- Removed redundant submitter id/name from POST response

## 260218

- Added DELETE area endpoint

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
- Added new endpoints for CA and STR, so they can get their own areas/activities (this will also streamline testing by CA and STR)
- Changed default sorting for GET into `createdAt`, descending

## 251228

- Evolved version of original prototype
