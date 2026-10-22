<h1>Activity (technical)</h1>

This document describes the **technical design** of SDEP activities.

Reference links:

- [Activity (functional)](./ACTIVITY_FUNC.md)
- [External API endpoints](./API_TECH.md#surface)
- [Internal data model](./DATAMODEL_TECH.md#activity)

The generic patterns behind the choices below are in [Architecture](./ARCHITECTURE_TECH.md) and [API](./API_TECH.md#code-structure).

<h2>Table of contents</h2>

- [Characteristics](#characteristics)
- [Data](#data)
  - [`Activity.Request`](#activityrequest)
  - [`Activity.Response`](#activityresponse)
  - [Schema names and envelope](#schema-names-and-envelope)
- [Data flow](#data-flow)
  - [`POST /activities/bulk`](#post-activitiesbulk)
  - [`GET /activities` (CA, AMA, STA)](#get-activities-ca-ama-sta)
- [Validation](#validation)
- [Code structure](#code-structure)
  - [File map](#file-map)
  - [Endpoint to service](#endpoint-to-service)
  - [Backport to v1](#backport-to-v1)
  - [Shared with other resources](#shared-with-other-resources)
  - [Runtime wiring](#runtime-wiring)

## Characteristics

For activity:

| Aspect      | Description                                                    |
| ----------- | -------------------------------------------------------------- |
| Owner       | Platform (STR)                                                 |
| Writers     | STR only                                                       |
| Write shape | One `POST /activities/bulk`                                    |
| Payload     | JSON                                                           |
| Readers     | CA (activities within own areas), STA and AMA (all activities) |
| Concurrency | No version token: a single writer per `activityId`             |
| Lifecycle   | `finished` or `cancelled`, set by the caller                   |
| Delete      | None: resubmit with `status` `cancelled`                       |

More things are specific to activities:

- Timestamps must be UTC (offset `Z` or `+00:00`; no other offsets, no date-only values), in STR v1 and v2
- A resubmitted `activityId` with other content is a correction: it versions the previous record instead of creating a duplicate
- An identical activity, with or without its `activityId`, returns the stored version and writes nothing, which makes the bulk write safe to retry (see [Idempotency](./ARCHITECTURE_TECH.md#idempotency))

## Data

**This is an overview, not the contract.** The contract is the OpenAPI document of the
version you call; the persisted columns are in [Internal data model](./DATAMODEL_TECH.md#activity).
The tables below name the fields and say what they are for.

---

### `Activity.Request`

Submitted by the platform (`POST /activities/bulk`).

| Field                | Description                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------- |
| `activityId`         | Functional ID identifying the activity (optionally supplied and versioned, else auto-generated **[1]**) |
| `activityName`       | Display name (optional)                                                                                 |
| `status`             | `finished` (default) or `cancelled`                                                                     |
| `areaId`             | Functional ID referencing the area the rental address is in                                             |
| `url`                | References the advertisement online                                                                     |
| `address`            | Rental address (the `Address` composite, shared with listings)                                          |
| `registrationNumber` | Registration number of the rental address                                                               |
| `numberOfGuests`     | Number of guests; must match the length of `countryOfGuests`                                            |
| `countryOfGuests`    | One ISO 3166-1 alpha-3 code per guest, or `N/A`                                                         |
| `temporal`           | The rental period (`startDatetime`, `endDatetime`); UTC                                                 |

[1] `activityId` belongs to one platform and is unique across all platforms, see [Identity](./DATAMODEL_TECH.md#identity). Each version of it has its own `createdAt`. A resubmitted ID with other content is a correction, see [characteristics](#characteristics). A generated ID is deterministic: an identical activity resent without an ID gets the same ID, see [ID management](./ARCHITECTURE_TECH.md#id-management).

---

### `Activity.Response`

Returned by every `GET /activities`, and embedded in every OK item of the bulk response.
It comprises the request fields, enriched by SDEP:

| Added field              | Description                                           |
| ------------------------ | ----------------------------------------------------- |
| `areaName`               | Copied from the referenced area                       |
| `competentAuthorityId`   | The authority owning that area                        |
| `competentAuthorityName` | Display name of that authority                        |
| `platformId`             | The submitting platform (not accepted on the request) |
| `platformName`           | Display name of that platform                         |
| `createdAt`              | The version timestamp, managed by SDEP                |

---

### Schema names and envelope

Dotted titles, as for listings:

```text
Activity  .Request | .Response | .BulkRequest | .BulkResultItem | .BulkResponse | .ListResponse | .CountResponse
```

- `Activity.Status` backs the `status` field (`app/enums.py`), titled that way in the OpenAPI document
- `Activity.BulkRequest.activities` uses `SkipValidation` per item, so one invalid item is NOK without failing the batch
- An OK item embeds `Activity.Response`, a NOK item embeds `errors`
- The HTTP status of the bulk result is 201 all OK, 200 partial, 422 all failed (`app/api/common/bulk_json.py`)

## Data flow

The write and the read, step by step. The four-step validation shape behind the write is in
[Validation](#validation); the generic rationale is in [Bulk](./ARCHITECTURE_TECH.md#bulk).
The read serves steps 4, 6 and 8 of the [sequence](./ACTIVITY_FUNC.md#sequence).

---

### `POST /activities/bulk`

A. Inputs:

- From JWT (verified by the auth dependency):
  - `clientId` ← `client_id` claim
  - `platformName` ← `client_name` claim
- From JSON payload:
  - `activities`: array of 1-1000 activity items; each item carries:
    - `activityId` (optional functional id, alphanumeric with hyphens, length \<= 64)
    - `activityName` (optional, length \<= 64)
    - `status` (optional enum, defaults to `finished`; may also be `cancelled`)
    - `areaId` (required functional id, must reference an existing area)
    - `url` (length \<= 2048)
    - `address` (composite: `thoroughfare`, `locatorDesignatorNumber` (optional), `locatorDesignatorLetter` (optional), `locatorDesignatorAddition` (optional), `postCode`, `postName`, `fullAddress`)
    - `registrationNumber` (length \<= 128)
    - `numberOfGuests` (1-1024)
    - `countryOfGuests` (array, 1-1024 elements; each ISO 3166-1 alpha-3 or `N/A`, uppercase; length must equal `numberOfGuests`)
    - `temporal` (composite: `startDatetime`, `endDatetime`, both UTC)

B. Steps:

1. Per-item Pydantic validation (`TypeAdapter(ActivityRequest)`):

   - Invalid items are marked NOK with their errors; valid items continue
   - The original client-supplied `activityId` (or `None`) is preserved for the response
   - For valid items, a missing `activityId` is generated after step 2, because the platform is part of it: a deterministic UUIDv8, see [ID management](./ARCHITECTURE_TECH.md#id-management). An ID whose activity is deactivated is skipped (the next generation).

2. Resolve or version the `Platform` once per batch (on a platform rename, its identity row is locked first, see [Locking](./ARCHITECTURE_TECH.md#locking)):

   - No row exists for `clientId`: create a new Platform
     - Technical id `id`: autogenerated (int)
     - Functional id `platformId`: auto-generated (UUIDv4)
     - Name `platformName`: ← JWT
     - Reference `clientId`: ← JWT
     - Timestamp `createdAt`: autogenerated (`now()`)
   - `clientId` exists and `platformName` unchanged: reuse as is
   - `clientId` exists and `platformName` changed: mark the current Platform as ended (`endedAt = now()`) and insert a new version
     - Technical id `id`: autogenerated (int)
     - Functional id `platformId`: same as is
     - Name `platformName`: ← JWT
     - Reference `clientId`: same as is
     - Timestamp `createdAt`: autogenerated (`now()`)
   - Only ended rows exist for `clientId`: reject as deactivated

3. Intra-batch deduplication on `activityId` (last-wins): when a batch contains multiple valid items with the same `activityId`, only the last occurrence proceeds; earlier occurrences are marked NOK with a "superseded by later item in batch at index N" error.

4. Referential integrity check (single query): resolve `areaId` → technical `id` (and owning CA) for all referenced areas via `get_area_ca_map`. Items pointing at unknown areas are marked NOK.

5. Resolve or version each `Activity` (row-locked `FOR UPDATE` on `(activityId, platformId)`):

   - An active row exists with the same content: the same activity was sent before (a retry), so the item is OK with the stored version, and nothing is written
   - An active row exists with other content: mark the current Activity as ended (`endedAt = now()`); the new version is inserted in step 6
   - No row exists: defer to step 6 (a new activity, with the supplied or generated functional id)
   - Only ended rows exist for this platform: reject as deactivated (a generated `activityId` never gets here, it moves to the next generation in step 2)

6. Bulk insert all remaining valid items in a single multi-row INSERT, using one `batch_created_at` (= `now()` at INSERT time) for the whole batch. Each new `activity` row:

   - Technical id `id`: autogenerated (int)
   - Functional id `activityId`: ← validated request (supplied, or generated UUIDv8 from step 2)
   - Functional columns from the payload (`activityName`, `status`, `url`, address fields, `registrationNumber`, `numberOfGuests`, `countryOfGuests`, temporal fields)
   - Platform reference `platform_id` (FK): ← technical `id` of the Platform row from step 2
   - Area reference `area_id` (FK): ← technical `id` resolved in step 4
   - Timestamp `createdAt`: ← `batch_created_at`
   - End timestamp `endedAt`: `NULL`

7. Commit at the API transaction boundary (CRUD layer only flushes); on any exception the whole batch rolls back.

8. Return a per-item OK/NOK response preserving the original request order. HTTP status: `201` if all items succeeded, `200` on partial success, `422` if all items failed.

Net effect:

- 1x new `platform` row inserted only when the platform is new or its name changed; the previous version is marked ended in the latter case
- N new `activity` rows (one per valid item that is not a retry), each with FKs `activity.platform_id → platform.id` and `activity.area_id → area.id`
- Optionally M old `activity` rows marked ended when an `activityId` had an active version with other content for this platform

---

### `GET /activities` (CA, AMA, STA)

A. Inputs:

- From JWT: the audience role plus `sdep_read`; for CA also `clientId`, which fixes the owner scope
- From the query string: `offset`, `limit`, and the filters that the domain declares, see [Filtering](./API_TECH.md#activities)

B. Steps:

1. The router checks the roles and fixes the scope, passed as the `client` argument of the read handler. The query string cannot change it.

   | Step | Actor | Domain     | Roles                   | Fixed scope                                         |
   | ---- | ----- | ---------- | ----------------------- | --------------------------------------------------- |
   | 4.   | CA    | CA v1, v2  | `sdep_ca`, `sdep_read`  | Own areas (`client` is the CA, from `clientId`)     |
   | 6.   | AMA   | AMA v1     | `sdep_ama`, `sdep_read` | None (`client=None`): all platforms and authorities |
   | 8.   | STA   | STA v1, v2 | `sdep_sta`, `sdep_read` | None (`client=None`): all platforms and authorities |

2. Parse pagination and filters. An invalid value (non-UTC timestamp, bad functional ID) is HTTP 400, the query does not run. CA v1 and v2 declare the same filters, and `limit` defaults to 1000, the maximum.

3. One query on the read-only session: current versions only (`endedAt IS NULL`), joined with `area` and `competent_authority`. Scope and filters are plain `WHERE` clauses, combined with AND.

4. Order newest first (`createdAt` desc, then technical `id` desc), then apply `offset` and `limit`.

5. Return `Activity.ListResponse`, one `Activity.Response` per activity. `GET /activities/count` runs the same query without order and paging, and returns `Activity.CountResponse`.

Net effect:

- No row is written
- Only the current version of an activity is returned, never its history; a `cancelled` activity is current too, and is returned

## Validation

`POST /activities/bulk` runs the four-step flow every bulk write in SDEP follows. The step
number says **when** a check runs:

1. **Syntax and semantics per item** (Pydantic): field formats, the guest cardinality, start before end (`value_error`)
2. **Referential integrity** (one query per batch): `areaId` exists (`not_found_error`), and the area must be regulated for activities (`regulation_error`)
3. **Versioning under lock**: `SELECT ... FOR UPDATE` on the current version, then mark it ended and insert the new one. A fully ended `activityId` is refused as deactivated
4. **Feedback**: per-item OK/NOK in the original order, a NOK item never fails the batch

Two things are specific to activities:

- **Intra-batch duplicates are last-wins**: of repeated `activityId`s in one batch only the last is processed, the earlier ones are NOK with "superseded by later item in batch at index N"
- **No version token**: the platform is the only writer, so there is nothing to collide with. Listings need one, see [Concurrency](./LISTING_TECH.md#concurrency)

The generic rationale behind the flow is in [Bulk](./ARCHITECTURE_TECH.md#bulk).

## Code structure

Activities are the oldest resource in SDEP, and the pattern every later resource copies.
Listings mirror this set one-for-one, see [Listing (technical)](./LISTING_TECH.md#file-map).

---

### File map

| Layer    | File                                  | What it holds                                                                   |
| -------- | ------------------------------------- | ------------------------------------------------------------------------------- |
| Models   | `app/models/activity.py`              | The `Activity` ORM class, its unique constraint and its check constraints       |
| Models   | `app/models/temporal.py`              | The `Temporal` composite (the rental period)                                    |
| Enums    | `app/enums.py`                        | `ActivityStatus`, titled `Activity.Status`                                      |
| Schemas  | `app/schemas/activity.py`             | `Activity.Request` and `Activity.Response`, plus the filters                    |
| Schemas  | `app/schemas/activity_bulk.py`        | The bulk request and response shapes                                            |
| CRUD     | `app/crud/activity.py`                | The queries: scoped read, count, locked current version, mark-ended plus insert |
| Services | `app/services/activity.py`            | The read service (list and count)                                               |
| Services | `app/services/activity_bulk.py`       | `POST /activities/bulk`, the four-step validation flow                          |
| API      | `app/api/common/activity_handlers.py` | The one read handler used by CA, STA and AMA                                    |
| API      | `app/api/common/activity_examples.py` | The OpenAPI examples and field text                                             |
| API      | `app/api/domains/<domain>/routers/`   | One router per audience and version                                             |

---

### Endpoint to service

The endpoint contract per domain and version is in [API](./API_TECH.md#surface).

| Endpoint                                   | Domain | Router                              | Service                                   |
| ------------------------------------------ | ------ | ----------------------------------- | ----------------------------------------- |
| `POST /activities/bulk`                    | STR v1 | `str/routers/activities_bulk_v1.py` | `activity_bulk.py`                        |
| `POST /activities/bulk`                    | STR v2 | `str/routers/activities_bulk_v2.py` | `activity_bulk.py`                        |
| `GET /activities`, `GET /activities/count` | CA v1  | `ca/routers/activities_v1.py`       | `activity.py`, via `activity_handlers.py` |
| `GET /activities`, `GET /activities/count` | CA v2  | `ca/routers/activities_v2.py`       | `activity.py`, via `activity_handlers.py` |
| `GET /activities`, `GET /activities/count` | STA v1 | `sta/routers/activities_v1.py`      | `activity.py`, via `activity_handlers.py` |
| `GET /activities`, `GET /activities/count` | STA v2 | `sta/routers/activities_v1.py`      | `activity.py`, via `activity_handlers.py` |
| `GET /activities`, `GET /activities/count` | AMA v1 | `ama/routers/activities_v1.py`      | `activity.py`, via `activity_handlers.py` |

The read handler takes the scope as its `client` argument: a `Client` scopes the read to
that competent authority, `None` makes it unscoped (STA and AMA). The argument is
keyword-only with no default, so an unscoped read has to be written out.

---

### Backport to v1

STR v2 introduced these rules, and STR v1 has them too, because v2 stays alpha longer:

- UTC-only timestamps
- The regulation check (`regulation_error`)
- Wider `url` (2048), `fullAddress` (328) and `registrationNumber` (128)

So STR v1 and v2 share one request schema, `Activity.Request`, and one service path. CA v1
documents the same response maximums as CA v2. The contract changes are listed in the
[changelog](../CHANGELOG.md).

---

### Shared with other resources

| Shared part                          | Where it comes from                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| The `Address` composite              | `app/models/address.py`, also used by listings                                        |
| The bulk HTTP status mapping         | `app/api/common/bulk_json.py`                                                         |
| The platform resolve and re-version  | `app/services/platform.py` (`ensure_platform`), also used by listings                 |
| The area lookup and regulation check | `get_area_ca_map()` plus `Regulation.covers()`, see [Area](./AREA_TECH.md#regulation) |
| The `StringArray` column type        | `app/models/types.py`, for `countryOfGuests`                                          |

---

### Runtime wiring

What is registered outside the activity files:

- Keycloak roles `sdep_str` for the writes, `sdep_ca`, `sdep_sta` and `sdep_ama` for the reads, plus `sdep_read` and `sdep_write`, in `keycloak/roles.yaml` and the `Role` enum
- Domain sub-app `/api/ama/v1`, with the same read handler and filters as STA v1 (`createdAtFrom`, `createdAtTo`, `areaId`, `platformId`, `competentAuthorityId`), see the [API surface](./API_TECH.md#activity-monitoring-authority-ama); a new sub-app follows the steps in [Adding a version](./API_TECH.md#adding-a-version)
- Audit action rules for the activity endpoints, in `app/security/audit.py`
- The bulk item schema `ActivityRequest` in `BULK_ITEM_SCHEMAS`, so the OpenAPI document keeps it as a component, see [OpenAPI document](./API_TECH.md#openapi-document)
- The `Activity` class in `app/models/__init__.py` and the module in `app/crud/__init__.py`
- The `activity` table, in the initial Alembic migration
- A test client per role, in `keycloak/machine-clients.yaml` and `scripts/generate-keycloak-machine-clients.py`, with the credentials exported by the root `Makefile`
- End-to-end tests `tests/test_*_activities*.py`, run by the `make test-<role>` targets and `scripts/run-tests.sh`
- The `activity` rows in `postgres/clean-testrun.sql` (test cleanup) and `postgres/count-app.sql`
