<h1>API Version Diff</h1>

Differences between consecutive API versions, generated from the committed OpenAPI
snapshots in `backend/tests/api/fixtures/`. Refresh with `make api-diff-update` from
`backend/`. Do not edit by hand.

For the versioning rules behind these differences, see [API](API.md).

## CA v1 to CA v2

| Category          | Added | Removed | Modified | Unchanged |
| ----------------- | ----- | ------- | -------- | --------- |
| Operations        | 0     | 0       | 2        | 5         |
| Component schemas | 0     | 0       | 0        | 13        |
| Security schemes  | 0     | 0       | 0        | 1         |

---

### Modified Operations

---

**`GET /activities`**

- Renamed `operationId` from `getActivityByCompetentAuthority` to `getActivityByCompetentAuthorityV2`
- Added optional query parameter `filterAreaId` (string)
- Added optional query parameter `filterCreatedAtFrom` (string, date-time)
- Added optional query parameter `filterCreatedAtTo` (string, date-time)
- Added optional query parameter `filterPlatformId` (string)
- Updated the endpoint description

---

**`GET /activities/count`**

- Renamed `operationId` from `countActivities` to `countActivitiesV2`
- Added optional query parameter `filterAreaId` (string)
- Added optional query parameter `filterCreatedAtFrom` (string, date-time)
- Added optional query parameter `filterCreatedAtTo` (string, date-time)
- Added optional query parameter `filterPlatformId` (string)
- Updated the endpoint description

---

### API Description

- CA v1: Endpoints for competent authorities to manage areas and to view activities. Status: stable. Superseded by CA v2 (beta).
- CA v2: Endpoints for competent authorities to manage areas and to view activities. Status: beta. Changes from CA v1: adds four optional activity filters (`filterCreatedAtFrom`, `filterCreatedAtTo`, `filterPlatformId`, `filterAreaId`) on the activity list and count endpoints; no other changes.
