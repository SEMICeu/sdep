<h1>API version diff</h1>

Differences between consecutive API versions, generated from the committed OpenAPI
snapshots in `backend/tests/api/fixtures/`. Refresh with `make api-diff-update` from
`backend/`. Do not edit by hand.

For the versioning rules behind these differences, see [API](API_TECH.md).

<h2>Table of Contents</h2>

- [CA v1 to v2](#ca-v1-to-v2)
  - [Added and removed operations](#added-and-removed-operations)
  - [Modified operations](#modified-operations)
  - [Component schemas](#component-schemas)
  - [API description](#api-description)
- [STR v1 to v2](#str-v1-to-v2)
  - [Added and removed operations](#added-and-removed-operations-1)
  - [Modified operations](#modified-operations-1)
  - [Component schemas](#component-schemas-1)
  - [API description](#api-description-1)
- [STA v1 to v2](#sta-v1-to-v2)
  - [Added and removed operations](#added-and-removed-operations-2)
  - [Component schemas](#component-schemas-2)
  - [API description](#api-description-2)

## CA v1 to v2

| Category          | Added | Removed | Modified | Unchanged |
| ----------------- | ----- | ------- | -------- | --------- |
| Operations        | 4     | 0       | 3        | 4         |
| Component schemas | 8     | 0       | 2        | 11        |
| Security schemes  | 0     | 0       | 0        | 1         |

---

### Added and removed operations

- Added `GET /listings`
- Added `GET /listings/count`
- Added `GET /platforms`
- Added `GET /platforms/count`

---

### Modified operations

---

**`GET /activities`**

- Renamed `operationId` from `getActivityByCompetentAuthority` to `getActivityByCompetentAuthorityV2`

---

**`GET /activities/count`**

- Renamed `operationId` from `countActivities` to `countActivitiesV2`

---

**`GET /areas`**

- Renamed `operationId` from `getOwnAreas` to `getOwnAreasV2`

---

### Component schemas

- Added `ListingCountResponse`
- Added `ListingFlag`
- Added `ListingListResponse`
- Added `ListingResponse`
- Added `ListingStatus`
- Added `PlatformCountResponse`
- Added `PlatformListResponse`
- Added `PlatformResponse`
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

### API description

- CA v1: Endpoints for competent authorities to manage areas and to view activities. Status: stable. Superseded by CA v2 (alpha).
- CA v2: Endpoints for competent authorities to manage areas, to view activities and platforms, and to view acknowledged listings (random checks). Status: alpha. Changes from CA v1: the activity response documents the field maximums (e.g. `url` 2048, `fullAddress` 328); adds `GET /listings` and `GET /listings/count` (acknowledged listings in own areas, random checks); adds `GET /platforms` and `GET /platforms/count`; no other changes.

## STR v1 to v2

| Category          | Added | Removed | Modified | Unchanged |
| ----------------- | ----- | ------- | -------- | --------- |
| Operations        | 4     | 0       | 2        | 2         |
| Component schemas | 16    | 3       | 3        | 10        |
| Security schemes  | 0     | 0       | 0        | 1         |

---

### Added and removed operations

- Added `GET /listings`
- Added `GET /listings/count`
- Added `POST /listing-acknowledgements/bulk`
- Added `POST /listings/bulk`

---

### Modified operations

---

**`GET /areas`**

- Renamed `operationId` from `getAreas` to `getAreasV2`
- Changed parameter `limit`: added `default` `1000`, updated the description, no longer accepts null
- Updated the endpoint description

---

**`POST /activities/bulk`**

- Renamed `operationId` from `postActivitiesBulk` to `postActivitiesBulkV2`
- Changed the request body
- Changed the `200` response
- Updated the endpoint description

---

### Component schemas

- Added `ActivityBulkRequestV2`
- Added `ActivityRequestV2`
- Added `CommonTemporalRequestV2`
- Added `ListingAcknowledgementBulkRequest`
- Added `ListingAcknowledgementBulkResponse`
- Added `ListingAcknowledgementBulkResultItem`
- Added `ListingAcknowledgementRequest`
- Added `ListingBulkRequest`
- Added `ListingBulkResponse`
- Added `ListingBulkResultItem`
- Added `ListingCountResponse`
- Added `ListingFlag`
- Added `ListingListResponse`
- Added `ListingRequest`
- Added `ListingResponse`
- Added `ListingStatus`
- Removed `ActivityBulkRequest`
- Removed `ActivityRequest`
- Removed `CommonTemporalRequest`
- Changed `ActivityResponse`
  - Property `countryOfGuests`: added `maxItems` `1024`, added `minItems` `1`, updated the description
  - Property `numberOfGuests`: added `maximum` `1024`, added `minimum` `1`
  - Property `registrationNumber`: added `maxLength` `32`, updated the description
  - Property `url`: added `maxLength` `2048`, updated the description
- Changed `CommonAddressRequest`
  - Property `fullAddress`: changed `maxLength` from `318` to `328`, updated the description
- Changed `CommonAddressResponse`
  - Property `fullAddress`: added `maxLength` `328`, updated the description
  - Property `locatorDesignatorAddition`: added `maxLength` `128`, updated the description
  - Property `locatorDesignatorLetter`: added `maxLength` `10`, updated the description
  - Property `locatorDesignatorNumber`: added `minimum` `0`, updated the description
  - Property `postCode`: added `maxLength` `10`, updated the description
  - Property `postName`: added `maxLength` `80`, updated the description
  - Property `thoroughfare`: added `maxLength` `80`, updated the description

---

### API description

- STR v1: Endpoints for short-term rental platforms to view areas and to submit activities. Status: stable. Superseded by STR v2 (alpha).
- STR v2: Endpoints for short-term rental platforms to view areas, to submit and acknowledge listings (random checks), and to submit activities. Status: alpha. Changes from STR v1: activity timestamps must be UTC (offset `Z` or `+00:00`; no other offsets, no date-only values); activity `url` and `fullAddress` allow 2048 and 328 characters (v1: 128 and 318); activities are rejected per item (`regulation_error`) for areas that are regulated for listing only; `GET /areas` returns at most 1000 areas per call (`limit` defaults to 1000); adds the listing endpoints for random checks (`POST /listings/bulk`, `GET /listings`, `GET /listings/count`, `POST /listing-acknowledgements/bulk`); no other changes.

## STA v1 to v2

| Category          | Added | Removed | Modified | Unchanged |
| ----------------- | ----- | ------- | -------- | --------- |
| Operations        | 2     | 0       | 0        | 8         |
| Component schemas | 5     | 0       | 0        | 18        |
| Security schemes  | 0     | 0       | 0        | 1         |

---

### Added and removed operations

- Added `GET /listings`
- Added `GET /listings/count`

---

### Component schemas

- Added `ListingCountResponse`
- Added `ListingFlag`
- Added `ListingListResponse`
- Added `ListingResponse`
- Added `ListingStatus`

---

### API description

- STA v1: Read-only endpoints for the statistics authority to view all registered activity data, platforms, competent authorities and areas. Status: stable. Superseded by STA v2 (alpha).
- STA v2: Read-only endpoints for the statistics authority to view all registered activity data, all listings (random checks), platforms, competent authorities and areas. Status: alpha. Changes from STA v1: adds `GET /listings` and `GET /listings/count` (all listings in every lifecycle status, random checks); no other changes.
