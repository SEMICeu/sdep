<h1>API Version Diff</h1>

Differences between consecutive API versions, generated from the committed OpenAPI
snapshots in `backend/tests/api/fixtures/`. Refresh with `make api-diff-update` from
`backend/`. Do not edit by hand.

For the versioning rules behind these differences, see [API](API.md).

## CA v1 to CA v2

| Category          | Added | Removed | Modified | Unchanged |
| ----------------- | ----- | ------- | -------- | --------- |
| Operations        | 0     | 0       | 3        | 4         |
| Component schemas | 0     | 0       | 2        | 11        |
| Security schemes  | 0     | 0       | 0        | 1         |

---

### Modified Operations

---

**`GET /activities`**

- Renamed `operationId` from `getActivityByCompetentAuthority` to `getActivityByCompetentAuthorityV2`
- Added optional query parameter `areaId` (string)
- Added optional query parameter `createdAtFrom` (string, date-time)
- Added optional query parameter `createdAtTo` (string, date-time)
- Added optional query parameter `platformId` (string)
- Changed parameter `limit`: added `default` `1000`, updated the description, no longer accepts null
- Updated the endpoint description

---

**`GET /activities/count`**

- Renamed `operationId` from `countActivities` to `countActivitiesV2`
- Added optional query parameter `areaId` (string)
- Added optional query parameter `createdAtFrom` (string, date-time)
- Added optional query parameter `createdAtTo` (string, date-time)
- Added optional query parameter `platformId` (string)
- Updated the endpoint description

---

**`GET /areas`**

- Renamed `operationId` from `getOwnAreas` to `getOwnAreasV2`
- Changed parameter `limit`: added `default` `1000`, updated the description, no longer accepts null
- Updated the endpoint description

---

### Component Schemas

- Changed `ActivityResponse`
  - Property `countryOfGuests`: added `maxItems` `1024`, added `minItems` `1`, updated the description
  - Property `numberOfGuests`: added `maximum` `1024`, added `minimum` `1`
  - Property `registrationNumber`: added `maxLength` `32`, updated the description
  - Property `url`: added `maxLength` `2048`, updated the description
- Changed `CommonAddressResponse`
  - Property `fullAddress`: added `maxLength` `328`, updated the description
  - Property `locatorDesignatorAddition`: added `maxLength` `128`, updated the description
  - Property `locatorDesignatorLetter`: added `maxLength` `10`, updated the description
  - Property `locatorDesignatorNumber`: added `minimum` `0`, updated the description
  - Property `postCode`: added `maxLength` `10`, updated the description
  - Property `postName`: added `maxLength` `80`, updated the description
  - Property `thoroughfare`: added `maxLength` `80`, updated the description

---

### API Description

- CA v1: Endpoints for competent authorities to manage areas and to view activities. Status: stable. Superseded by CA v2 (beta).
- CA v2: Endpoints for competent authorities to manage areas and to view activities. Status: beta. Changes from CA v1: adds four optional activity filters (`createdAtFrom`, `createdAtTo`, `platformId`, `areaId`) on the activity list and count endpoints; `GET /areas` and `GET /activities` return at most 1000 records per call (`limit` defaults to 1000); the activity response documents the field maximums (e.g. `url` 2048, `fullAddress` 328); no other changes.

## STR v1 to STR v2

| Category          | Added | Removed | Modified | Unchanged |
| ----------------- | ----- | ------- | -------- | --------- |
| Operations        | 0     | 0       | 2        | 2         |
| Component schemas | 3     | 3       | 0        | 13        |
| Security schemes  | 0     | 0       | 0        | 1         |

---

### Modified Operations

---

**`GET /areas`**

- Renamed `operationId` from `getAreas` to `getAreasV2`
- Changed parameter `limit`: added `default` `1000`, updated the description, no longer accepts null
- Updated the endpoint description

---

**`POST /activities/bulk`**

- Renamed `operationId` from `postActivitiesBulk` to `postActivitiesBulkV2`
- Changed the request body
- Updated the endpoint description

---

### Component Schemas

- Added `ActivityBulkRequestV2`
- Added `ActivityRequestV2`
- Added `CommonTemporalRequestV2`
- Removed `ActivityBulkRequest`
- Removed `ActivityRequest`
- Removed `CommonTemporalRequest`

---

### API Description

- STR v1: Endpoints for short-term rental platforms to view areas and to submit activities. Status: stable. Superseded by STR v2 (beta).
- STR v2: Endpoints for short-term rental platforms to view areas and to submit activities. Status: beta. Changes from STR v1: activity timestamps must be UTC (offset `Z` or `+00:00`, no date-only values); activities are rejected per item (`regulation_error`) for areas that are regulated for listing only; `GET /areas` returns at most 1000 areas per call (`limit` defaults to 1000); no other changes.
