<h1>Listing (technical)</h1>

This document describes the **technical design** of SDEP listings (random checks).

Reference links:

- [Listing (functional)](./LISTING_FUNC.md)
- [External API endpoints](./API_TECH.md#surface)
- [Internal data model](./DATAMODEL_TECH.md#listing)

The generic patterns behind the choices below are in [Architecture](./ARCHITECTURE_TECH.md) and [API](./API_TECH.md#code-structure).

<h2>Table of contents</h2>

- [Characteristics](#characteristics)
- [Data](#data)
  - [`Listing.Request`](#listingrequest)
  - [`ListingScreening.Request`](#listingscreeningrequest)
  - [`ListingAcknowledgement.Request`](#listingacknowledgementrequest)
  - [`Listing.Response`](#listingresponse)
  - [Schema names and envelope](#schema-names-and-envelope)
- [Data flow](#data-flow)
  - [`POST /listings/bulk` (STR)](#post-listingsbulk-str)
  - [`POST /listing-screenings/bulk` (LSA)](#post-listing-screeningsbulk-lsa)
  - [`POST /listing-acknowledgements/bulk` (STR)](#post-listing-acknowledgementsbulk-str)
  - [`GET /listings` (all audiences)](#get-listings-all-audiences)
- [Transitions](#transitions)
- [Validation](#validation)
- [Concurrency](#concurrency)
- [Code structure](#code-structure)
  - [File map](#file-map)
  - [Endpoint to service](#endpoint-to-service)
  - [Shared with other resources](#shared-with-other-resources)
  - [Runtime wiring](#runtime-wiring)

See also the [bulk design](./ARCHITECTURE_TECH.md#bulk) in the technical architecture.

## Characteristics

For listing:

| Aspect      | Description                                             |
| ----------- | ------------------------------------------------------- |
| Owner       | Platform (STR)                                          |
| Writers     | STR > LSA > STR                                         |
| Write shape | Three `POST /<what-is-sent>/bulk`, one per state change |
| Payload     | JSON                                                    |
| Readers     | STR, CA, LSA, LMA and STA, each with a fixed scope      |
| Concurrency | Optimistic, on the `createdAt` version token            |
| Lifecycle   | `pending` to `clear` or `flagged` to `acknowledged`     |
| Delete      | None: every state change is a new version               |

Approach:

- POST follows the same logic as STR activities, including bulk and REST noun-based collection URLs
- GET follows the same logic as the CA v2 activity reads, including query filters for date, platform and area
- The EU-harmonized API (STR) is separated from the country-specific implementation (LSA, CA, LMA, STA)

**Where the screening authority sits.** The listing screening authority (LSA) implements step 4 within SDEP.
It can be SDEP itself, or an external system querying and feeding the `lsa` endpoints.
Either way the screening stays inside SDEP, so the data point
between platform and SDEP remains the listing and its registration number. That conforms to
the [EU Traveltech position paper](./LISTING_FUNC.md#traveltech).

---

**Design decisions**

A listing is **one thing with a lifecycle** (see [States](./LISTING_FUNC.md#states)): reading it is always `GET /listings`, and every arrow in the state diagram is one `POST`.

| Decision                                                    | Motivation                                                                                                                                                                                  |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| One read endpoint for everyone: `GET /listings`             | A listing keeps its `listingId` while it moves through the states. The state is fixed per audience (STR, CA, ...).                                                                          |
| One `Listing.Response` for every audience                   | Scope narrows which listings, never which fields; no field is audience-confidential (as `Activity.Response`). Audience-only data would get its own schema.                                  |
| One `POST` per state change, named after what is sent       | `/listings`, `/listing-screenings`, `/listing-acknowledgements` say what the caller sends, not what the listing becomes.                                                                    |
| The LSA always sends a screening result, not only "flagged" | The `pending -> clear` step needs a write too.                                                                                                                                              |
| A `/bulk` on every write                                    | One invalid item must not fail the batch, and the caller must know which item failed and why. Same as `POST /activities/bulk`.                                                              |
| Filters are named after the field they filter on            | `?status=flagged`, `?flags=UDS,EXP`, `?createdAtFrom=...`: the query parameter name is the response field name (ranges add `From`/`To`). Same convention as the (CA v2) activity endpoints. |
| Filters are declared per audience, never refused at runtime | Each audience has its own API and OpenAPI document; a filter it may not use is simply not declared there.                                                                                   |
| Data scope comes from the bearer token, not from a filter   | A platform sees its own listings, a competent authority its own areas, LSA/LMA/STA everything - decided by `client_id`. A caller cannot widen its scope with a filter.                      |
| API names are not database names                            | Three `POST` lists outside, one `Listing` table inside, where every `POST` adds a version of the same listing. See [Transitions](#transitions).                                             |
| The STR read has no `status` filter                         | An STR does not need the full lifecycle of its own listings; the router fixes `flagged`. It can still be added later, backward compatibly.                                                  |

Filters are listed per audience in [API](./API_TECH.md#filtering); they are declared in the
router, so an audience's OpenAPI document shows exactly the filters it may use.

## Data

**This is an overview, not the contract.** The contract is the OpenAPI document of the
version you call; the persisted columns are in [Internal data model](./DATAMODEL_TECH.md#listing).
The tables below name the fields and say what they are for.

Schemas describe the **resource**; bulk and list schemas describe the **transport envelope**,
following the Activity pattern (`Activity.Request`, `Activity.Response`, `Activity.BulkRequest`,
`Activity.BulkResultItem`, `Activity.BulkResponse`, `Activity.ListResponse`,
`Activity.CountResponse`). No endpoint-specific schemas.

---

### `Listing.Request`

Submitted by the platform (`POST /listings/bulk`).

| Field                       | Description                                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------------------------- |
| `listingId`                 | Functional ID identifying the listing (optionally supplied/versioned, else auto-generated **[1][2]**) |
| `listingName`               | Display name (optional)                                                                               |
| `areaId`                    | Functional ID referencing the area where the listing is posted                                        |
| `url`                       | References the listing online                                                                         |
| `address`                   | Listing address (same composite as activities)                                                        |
| `declaredAsShortTermRental` | Host self-declaration (yes/no)                                                                        |
| `registrationNumber`        | Listing registration number (optional)                                                                |

[1] This allows the listing to be submitted as either:

- A correction (same id): allowed in `pending` only, creates a new version that stays `pending`
- A recurrence of the listing in a new random check (new id)

[2] `listingId` is unique per platform (as `activityId`), not globally.

---

### `ListingScreening.Request`

Submitted by the LSA (`POST /listing-screenings/bulk`), one bulk item per screened listing. The LSA does not POST the listing back, just the id with the result (same as `areaId` in `str: POST /activities/bulk`)

| Field        | Description                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------- |
| `platformId` | The submitting platform (`listingId` is only unique within a platform)                      |
| `listingId`  | The screened listing                                                                        |
| `createdAt`  | The version that was screened, see [Concurrency](./LISTING_TECH.md#concurrency)             |
| `flags`      | Zero or more [flag codes](#listingresponse); empty means `clear`, non-empty means `flagged` |

---

### `ListingAcknowledgement.Request`

Submitted by the STR platform (`POST /listing-acknowledgements/bulk`), one bulk item per flagged listing.

| Field       | Description                                                                      |
| ----------- | -------------------------------------------------------------------------------- |
| `listingId` | The flagged listing (scoped to the authenticated platform)                       |
| `createdAt` | The version being acknowledged, see [Concurrency](./LISTING_TECH.md#concurrency) |

The acknowledgement carries no further data (see sequence footnote 6.[4]).

---

### `Listing.Response`

Returned by every `GET /listings`, and embedded in every OK item of the [three bulk responses](#schema-names-and-envelope). Comprises the request fields, enriched with:

| Field                    | Description                                                                                            |
| ------------------------ | ------------------------------------------------------------------------------------------------------ |
| `status`                 | Lifecycle status: `pending`, `clear`, `flagged`, `acknowledged`                                        |
| `flags`                  | **Flag codes** raised by screening (empty until screened, non-empty when screened/status is `flagged`) |
| `submittedAt`            | Timestamp of the platform's submission (UTC); unchanged by screening and acknowledgement               |
| `screenedAt`             | Timestamp of the screening (optional, UTC)                                                             |
| `acknowledgedAt`         | Timestamp of the acknowledgement (optional, UTC)                                                       |
| `areaName`               | Display name of the area (optional)                                                                    |
| `competentAuthorityId`   | Functional ID of the competent authority that owns the area                                            |
| `competentAuthorityName` | Display name of the competent authority (optional)                                                     |
| `platformId`             | Functional ID of the submitting platform                                                               |
| `platformName`           | Display name of the platform (optional)                                                                |
| `createdAt`              | Timestamp when this listing version was created (UTC)                                                  |

This schema is the same for every audience. Which fields carry a value, follows from the listing's state (see the fixed scopes per audience under [Endpoints](./API_TECH.md#surface)).

---

**Flag Codes**

| Code  | Synopsis (description)         | Declared as STR | Registration Number Present | Registration Number Known | Registration Number Valid | Address Matches Registration | Private Residence |
| ----- | ------------------------------ | :-------------: | :-------------------------: | :-----------------------: | :-----------------------: | :--------------------------: | :---------------: |
| `ABS` | Absent Registration Number     |       Yes       |             No              |             -             |             -             |              -               |         -         |
| `UNK` | Unknown Registration Number    |       Yes       |             Yes             |            No             |             -             |              -               |         -         |
| `EXP` | Expired Registration Number    |       Yes       |             Yes             |            Yes            |            No             |              -               |         -         |
| `MIS` | Mismatched Address             |       Yes       |             Yes             |            Yes            |            Yes            |              No              |         -         |
| `NPR` | Not a Private Residence        |       Yes       |             Yes             |            Yes            |            Yes            |             Yes              |        No         |
| `UNX` | Unexpected Registration Number |       No        |             Yes             |             -             |             -             |              -               |         -         |
| `UDS` | Undeclared Short-Term Rental   |       No        |             No              |             -             |             -             |              -               |        Yes        |

*The value "-" denotes "not applicable" (because the decision is already taken based on the other values).*

*For code UDS, the "private residence yes" is expected to be determined by matching the listing address details with a corresponding record in an external system.*

---

### Schema names and envelope

Dotted titles, similar to the existing OpenAPI specification (`model_config = ConfigDict(title="Activity.Request")`):

```text
Listing                 .Request | .Response | .BulkRequest | .BulkResultItem | .BulkResponse | .ListResponse | .CountResponse
ListingScreening        .Request | .BulkRequest | .BulkResultItem | .BulkResponse
ListingAcknowledgement  .Request | .BulkRequest | .BulkResultItem | .BulkResponse
```

Two enums back the fields inside these schemas, as `Activity.Status` does for activities (`app/enums.py`):

- `Listing.Status` - type of the `status` field in `Listing.Response` (`pending`, `clear`, `flagged`, `acknowledged`)
- `Listing.Flag` - type of each item in `flags`, in `Listing.Response` and `ListingScreening.Request` (the seven [flag codes](#listingresponse))

The three bulk responses and what an OK item embeds:

| Endpoint                              | Bulk response                         | OK item embeds                                           |
| ------------------------------------- | ------------------------------------- | -------------------------------------------------------- |
| `POST /listings/bulk`                 | `Listing.BulkResponse`                | `Listing.Response`, the new `pending` version            |
| `POST /listing-screenings/bulk`       | `ListingScreening.BulkResponse`       | `Listing.Response`, the new `clear` or `flagged` version |
| `POST /listing-acknowledgements/bulk` | `ListingAcknowledgement.BulkResponse` | `Listing.Response`, the new `acknowledged` version       |

- A NOK item embeds `errors` instead, as `Activity.BulkResultItem` does today
- Because every OK item returns the listing as it now is, there is no `ListingScreening.Response` or `ListingAcknowledgement.Response`
- `Listing.BulkRequest.listings` uses `SkipValidation` per item, as `Activity.BulkRequest`, so one invalid item can be NOK without failing the batch

---

## Data flow

The three writes and the read, step by step. The writes follow the four-step bulk flow of
[`POST /activities/bulk`](./ACTIVITY_TECH.md#post-activitiesbulk); what differs per write
is called out below. Two of them add a step activities do not have: the **version token**,
see [Concurrency](#concurrency). The read serves steps 4, 5, 8, 10 and 12 of the
[sequence](./LISTING_FUNC.md#sequence), one flow for every audience.

---

### `POST /listings/bulk` (STR)

A. Inputs:

- From JWT: `clientId` and `platformName` identify the submitting platform (roles `sdep_str`, `sdep_write`)
- From the JSON payload, per item: the `Listing.Request` fields, see [Data](#data)

B. Steps:

1. Per-item Pydantic validation, as for activities. Invalid items are NOK, the batch continues. A missing `listingId` is auto-generated (UUIDv4).
2. Resolve or version the `Platform` once per batch (`ensure_platform`), exactly as the activity bulk does.
3. Intra-batch deduplication on `listingId` (last-wins), as the activity bulk does: earlier occurrences are NOK (`duplicate_error`, "superseded by later item in batch at index N").
4. Referential integrity, one query per batch: `areaId` must exist (`not_found_error`) and the area must be regulated for listings (`regulation_error`), see [Regulation](./AREA_TECH.md#regulation).
5. Resolve each `Listing` row-locked (`FOR UPDATE` on `(listingId, platformId)`). No current version means a new listing; a current version must be `pending`, else NOK (`conflict_error`). No version token here: the platform corrects its own `pending` listing, and the only thing that can interfere is the screening authority getting there first, which this check catches.
6. Mark any current version ended (`endedAt = now()`) and insert the next version: `status` is `pending`, `submittedAt` is set, `flags` is empty.
7. Commit at the API transaction boundary; per-item OK/NOK in the original order, every OK item embedding the listing as it now is.

Net effect:

- 1 new `platform` row only when the platform is new or its name changed
- N new `listing` rows, each with FKs to `platform` and `area`
- Optionally M old `listing` rows marked ended, where a resubmitted `listingId` had a current version

---

### `POST /listing-screenings/bulk` (LSA)

A. Inputs:

- From JWT: `clientId` identifies the listing screening authority (role `sdep_lsa`)
- From the JSON payload, per item: `platformId`, `listingId`, `createdAt` (the version the screening refers to), `flags` (may be empty)

B. Steps:

1. Per-item Pydantic validation, as for activities. Invalid items are NOK, the batch continues.

2. Intra-batch deduplication on `(platformId, listingId)` (last-wins): earlier occurrences are NOK (`duplicate_error`).

3. Resolve the platforms once per batch (`get_current_by_platform_ids`): the screening authority names the platform, it does not own it. An unknown `platformId` marks its items NOK.

4. Referential integrity: the listing must exist for `(platformId, listingId)`, otherwise NOK (`not_found_error`).

5. Resolve each `Listing` row-locked (`FOR UPDATE` on `(listingId, platformId)`), then check on the **locked** version:

   - The submitted `createdAt` equals the current version's `createdAt`, otherwise NOK (`conflict_error`, `loc: ["createdAt"]`)
   - The current status is `pending` (initial screening) or `clear` / `flagged` (correction); `acknowledged` is refused (`conflict_error`)

   Both checks must run after the lock: a state change creates a new version, so a value read before the lock would be stale.

6. Mark the current version ended (`endedAt = now()`) and insert the next version, as for activities. The new version carries `screenedAt`, the submitted `flags`, and the status derived from them: `flagged` when flags are present, `clear` when not. `submittedAt` is copied forward.

7. Commit at the API transaction boundary; per-item OK/NOK response in the original order, every OK item embedding the listing as it now is.

Net effect:

- M old `listing` rows marked ended, M new `listing` rows inserted (one version per screened listing)
- No `platform` row is written: the screening authority resolves platforms, it never creates or versions them

---

### `POST /listing-acknowledgements/bulk` (STR)

A. Inputs:

- From JWT: `clientId` identifies the platform, which must own the listings (roles `sdep_str`, `sdep_write`)
- From the JSON payload, per item: `listingId`, `createdAt` (the version acknowledged)

B. Steps:

1. Per-item Pydantic validation: `listingId` format, `createdAt` a UTC timestamp.
2. Intra-batch deduplication on `listingId` (last-wins): earlier occurrences are NOK (`duplicate_error`).
3. Referential integrity: the listing must exist for the authenticated platform (`not_found_error`). No platform resolution step: the platform is the owner, resolved from the token.
4. Resolve each `Listing` row-locked, then check on the locked version: `createdAt` is still current (`conflict_error`), and the status is `flagged` (`conflict_error`).
5. Mark the current version ended and insert the next version: `status` is `acknowledged`, `acknowledgedAt` is set, the `flags` are copied forward so the screening outcome is retained.
6. Commit at the API transaction boundary; per-item OK/NOK as above.

Net effect:

- M old `listing` rows marked ended, M new `listing` rows inserted
- No `platform` row is written
- A retried acknowledgement fails on the version token, which the platform reads as "already acknowledged", see [Transitions](#transitions)

---

### `GET /listings` (all audiences)

A. Inputs:

- From JWT: the audience role plus `sdep_read`; for STR and CA also `clientId`, which fixes the owner scope
- From the query string: `offset`, `limit` (default and maximum 1000), and the filters that the audience declares, see [Filtering](./API_TECH.md#listings)

B. Steps:

1. The router checks the roles and fixes the `ListingScope`. The query string cannot change it.

   | Step | Actor | Domain | Roles                   | Fixed scope                                                  |
   | ---- | ----- | ------ | ----------------------- | ------------------------------------------------------------ |
   | 4.   | LSA   | LSA v2 | `sdep_lsa`, `sdep_read` | All platforms, `status` is `pending`                         |
   | 5.   | STR   | STR v2 | `sdep_str`, `sdep_read` | Own platform (`clientId`), `status` is `flagged`             |
   | 8.   | CA    | CA v2  | `sdep_ca`, `sdep_read`  | Own areas (`clientId` of the CA), `status` is `acknowledged` |
   | 10.  | LMA   | LMA v2 | `sdep_lma`, `sdep_read` | None: all platforms and competent authorities, every status  |
   | 12.  | STA   | STA v2 | `sdep_sta`, `sdep_read` | None: all platforms and competent authorities, every status  |

2. Parse pagination and filters. An invalid value (unknown flag code, non-UTC timestamp, bad functional ID) is HTTP 400, the query does not run.

3. One query on the read-only session: current versions only (`endedAt IS NULL`), joined with `platform`, `area` and `competent_authority`. Scope and filters are plain `WHERE` clauses, combined with AND.

4. Order newest first (`createdAt` desc, then technical `id` desc), then apply `offset` and `limit`.

5. Return `Listing.ListResponse`, one `Listing.Response` per listing. `GET /listings/count` runs the same query without order and paging, and returns `Listing.CountResponse`.

Net effect:

- No row is written
- Only the current version of a listing is returned, never its history
- The CA gets only acknowledged listings in its own areas, so it acts on listings that the platform has seen and acknowledged

## Transitions

**Every transition is a new version** (mark the current version ended, insert the new one), reusing the activity versioning machinery (`bulk_mark_as_ended` + insert under `FOR UPDATE`). No listing row is ever updated in place.

Every new version gets a new `createdAt` (the version timestamp). The actor timestamps below are set by the write that owns them and copied forward otherwise.

| Transition                                   | Actor | Precondition (current version)        | In new version                     |
| -------------------------------------------- | ----- | ------------------------------------- | ---------------------------------- |
| `POST /listings/bulk`                        | STR   | none                                  | `pending`, `submittedAt`           |
| `POST /listings/bulk` (correction)           | STR   | `pending`                             | `pending`, `submittedAt`           |
| `POST /listing-screenings/bulk`              | LSA   | `pending`; version matches            | `clear` or `flagged`, `screenedAt` |
| `POST /listing-screenings/bulk` (correction) | LSA   | `clear` or `flagged`; version matches | `clear` or `flagged`, `screenedAt` |
| `POST /listing-acknowledgements/bulk`        | STR   | `flagged`; version matches            | `acknowledged`, `acknowledgedAt`   |

There is no "acknowledgement (correction)": it carries no data. An accidentally retried acknowledgement carries the `flagged` version's `createdAt`, which is no longer current, and is refused with `conflict_error`; the platform treats that as "already acknowledged".

A failed precondition is a per-item NOK (`conflict_error`), see [Concurrency](#concurrency).

Motivation:

- Each actor may correct its own contribution while the listing is in the state it owns, so fields are rewritten; versioning is the established mechanism for "rewrite with history"
- `createdAt` is purely the version timestamp, as for activities, and doubles as the concurrency token; the actor timestamps (`submittedAt`, `screenedAt`, `acknowledgedAt`) are separate fields
- Every read filter is a plain `WHERE` on one table; history is available for reporting

Rejected alternatives:

- *Enrichment columns updated in place* (`flags`, `screenedAt`, `acknowledgedAt` written on the current row): simplest while the columns were write-once; once corrections rewrite them, in-place updates lose history and are the only UPDATE of business data in the model. Fallback if version volume ever matters.
- *Separate `ListingScreening` and `ListingAcknowledgement` classes* (insert-only): two extra tables, a "latest screening" join on every read, and a functional-id question for records that do not need one.
- *Copy the listing on screening* (a separate flagged record): breaks ID correlation.

---

## Validation

All three POST (writes) use the four-step flow of `POST /activities/bulk`:

1. Syntax and semantics per item (Pydantic)
2. Referential integrity (one query per batch)
3. Versioning: checks on the locked current version (`SELECT ... FOR UPDATE`, as `get_current_by_activity_ids` does for activities), then mark it ended and insert the new version
4. Feedback: per-item OK/NOK with the resulting `Listing.Response` (a NOK item does not fail the batch)

The response is 201 (all items OK), 200 (some OK) or 422 (all failed), with `succeeded`/`failed` counts and per-item feedback.

Intra-batch duplicates are last-wins in all three writes, as for activities: of repeated keys in one batch only the last is processed, the earlier ones are NOK (`duplicate_error`). The key is `listingId`, for screenings `(platformId, listingId)`.

The step number says **when** a check runs. Step 3 checks must run on the locked current version: a state change creates a new version, so a state or `createdAt` read before the lock would be stale.

For `POST /listings/bulk`:

- Step 1 - all `Listing.Request` fields are syntactically and semantically valid (`value_error`)
- Step 2 - `areaId` exists (`not_found_error`) and `Area.regulation` is in (`listing`, `all`) (`regulation_error`) **[1]**
- Step 3 - state precondition: no current version for `listingId` (new listing), or the current version is `pending` (correction) (`conflict_error`)
- No version token: the platform corrects its own `pending` listing, and the only thing that can interfere is the LSA screening it first, which the state precondition catches

For `POST /listing-screenings/bulk`:

- Step 1 - `platformId` and `listingId` match the functional ID format, `createdAt` is a UTC timestamp, every code in `flags` is a known [flag code](#listingresponse) (`value_error`)
- Step 2 - the listing exists for `platformId` + `listingId` (`not_found_error`)
- Step 3 - `createdAt` is the current version (`conflict_error`), see [Concurrency](#concurrency)
- Step 3 - state precondition: `pending` (initial screening), `clear` or `flagged` (correction); `acknowledged` is refused (`conflict_error`), see [Transitions](#transitions)

For `POST /listing-acknowledgements/bulk`:

- Step 1 - `listingId` matches the functional ID format, `createdAt` is a UTC timestamp (`value_error`)
- Step 2 - the listing exists for the authenticated platform (`not_found_error`)
- Step 3 - `createdAt` is the current version (`conflict_error`); a retried acknowledgement fails here, see [Transitions](#transitions)
- Step 3 - state precondition: `flagged` (`conflict_error`)

[1] The activity bulk RI check (STR v2) does the same for activity regulation. Both share the unfiltered `get_area_ca_map(session, ids)` lookup and check `Regulation.covers()` afterwards, so a regulation mismatch gets its own message (`regulation_error`) instead of `not_found_error`.

---

## Concurrency

The screening window is external and asynchronous, so no database lock can cover it. A platform may correct a listing (new `pending` version) while the LSA is screening the previous version, and the LSA may re-screen while a platform is acknowledging. The flags of one version must never land on another.

Optimistic concurrency, using the version timestamp that every response already carries:

- `ListingScreening.Request` and `ListingAcknowledgement.Request` carry the `createdAt` of the version they refer to
- Step 3 locks the current version and compares; mismatch = per-item NOK with `type: conflict_error`, `loc: ["createdAt"]`
- No retry path is needed (a retried acknowledgement is refused as no longer current, see [Transitions](#transitions)): the corrected listing is still `pending` and appears in the LSA's next `GET /listings` (fixed `pending` scope) with its new data; the re-screened listing is `flagged` again and appears in the platform's next `GET /listings`

Example bulk result item:

```json
{
  "listingIndex": 3,
  "listingId": "abc-123",
  "status": "NOK",
  "errors": {
    "detail": [
      {
        "msg": "Listing 'abc-123' version '2026-09-07T08:00:00Z' is no longer current",
        "type": "conflict_error",
        "loc": ["createdAt"]
      }
    ]
  }
}
```

---

## Code structure

Listings mirror the activity set one-for-one. Anyone who knows the activity code knows
where to look: same layers, same file names, same four-step bulk flow.

---

### File map

| Layer    | File                                           | What it holds                                                                   |
| -------- | ---------------------------------------------- | ------------------------------------------------------------------------------- |
| Models   | `app/models/listing.py`                        | The `Listing` ORM class, its unique constraint and its check constraints        |
| Enums    | `app/enums.py`                                 | `ListingStatus` and `ListingFlag`, titled `Listing.Status` and `Listing.Flag`   |
| Schemas  | `app/schemas/listing.py`                       | `Listing.Request` and `Listing.Response`, the filters and the scope object      |
| Schemas  | `app/schemas/listing_bulk.py`                  | The three bulk request and response shapes                                      |
| CRUD     | `app/crud/listing.py`                          | The queries: scoped read, count, locked current version, mark-ended plus insert |
| Services | `app/services/listing.py`                      | The read service (list and count)                                               |
| Services | `app/services/listing_bulk.py`                 | `POST /listings/bulk` (submit and correct)                                      |
| Services | `app/services/listing_screening_bulk.py`       | `POST /listing-screenings/bulk`                                                 |
| Services | `app/services/listing_acknowledgement_bulk.py` | `POST /listing-acknowledgements/bulk`                                           |
| Services | `app/services/listing_bulk_common.py`          | What the three bulk services share: per-item parsing, feedback, error messages  |
| API      | `app/api/common/listing_handlers.py`           | The one read handler used by every audience                                     |
| API      | `app/api/common/listing_filters.py`            | The query-parameter types, so every domain describes them identically           |
| API      | `app/api/common/listing_examples.py`           | The OpenAPI examples and field text                                             |
| API      | `app/api/domains/<domain>/routers/`            | One router per audience, holding the role check and the fixed scope             |
| Database | `backend/alembic/versions/008_add_listing.py`  | The `listing` table and its enum type                                           |

---

### Endpoint to service

| Endpoint                               | Domain | Router                                            | Service                                 |
| -------------------------------------- | ------ | ------------------------------------------------- | --------------------------------------- |
| `POST /listings/bulk`                  | STR v2 | `str/routers/listings_bulk_v2.py`                 | `listing_bulk.py`                       |
| `POST /listing-screenings/bulk`        | LSA v2 | `lsa/routers/listing_screenings_bulk_v2.py`       | `listing_screening_bulk.py`             |
| `POST /listing-acknowledgements/bulk`  | STR v2 | `str/routers/listing_acknowledgements_bulk_v2.py` | `listing_acknowledgement_bulk.py`       |
| `GET /listings`, `GET /listings/count` | STR v2 | `str/routers/listings_v2.py`                      | `listing.py`, via `listing_handlers.py` |
| `GET /listings`, `GET /listings/count` | LSA v2 | `lsa/routers/listings_v2.py`                      | `listing.py`, via `listing_handlers.py` |
| `GET /listings`, `GET /listings/count` | CA v2  | `ca/routers/listings_v2.py`                       | `listing.py`, via `listing_handlers.py` |
| `GET /listings`, `GET /listings/count` | LMA v2 | `lma/routers/listings_v2.py`                      | `listing.py`, via `listing_handlers.py` |
| `GET /listings`, `GET /listings/count` | STA v2 | `sta/routers/listings_v2.py`                      | `listing.py`, via `listing_handlers.py` |

The endpoint contract per domain and version is in [API](./API_TECH.md#surface).

Five audiences, one read service. The router is the only place the audience shows up: it
fixes the `ListingScope` (owner and/or lifecycle status) from the bearer token, and
declares the filters that audience may use. See
[Routers](./API_TECH.md#routers) for the general pattern.

---

### Shared with other resources

Nothing below was written twice:

| Shared part                              | Where it comes from                                                         |
| ---------------------------------------- | --------------------------------------------------------------------------- |
| The `Address` composite                  | `app/models/address.py`, reused as-is                                       |
| The bulk HTTP status mapping             | `app/api/common/bulk_json.py` (201 all OK, 200 partial, 422 all failed)     |
| The platform resolve and re-version step | `app/services/platform.py` (`ensure_platform`)                              |
| The area lookup and regulation check     | `get_area_ca_map()` plus `Regulation.covers()`, as the STR v2 activity bulk |
| The versioning machinery                 | `bulk_mark_as_ended` plus insert under `SELECT ... FOR UPDATE`              |
| The `StringArray` column type            | `app/models/types.py`, as `countryOfGuests`                                 |

---

### Runtime wiring

What is registered outside the listing files:

- Keycloak roles `sdep_lsa` and `sdep_lma`, next to the existing `sdep_str`, `sdep_ca` and `sdep_sta`, in `keycloak/roles.yaml` and the `Role` enum
- Domain sub-apps `/api/lsa/v2` and `/api/lma/v2`; the STR, CA and STA listing endpoints live in STR v2, CA v2 and STA v2, all alpha, see [Design](./API_TECH.md#design); a new sub-app follows the steps in [Adding a version](./API_TECH.md#adding-a-version)
- Audit action rules for the listing endpoints, in `app/security/audit.py`
- The bulk item schemas `ListingRequest`, `ListingScreeningRequest` and `ListingAcknowledgementRequest` in `BULK_ITEM_SCHEMAS`, so the OpenAPI document keeps them as components, see [OpenAPI document](./API_TECH.md#openapi-document)
- The `Listing` class in `app/models/__init__.py` and the module in `app/crud/__init__.py`
- The `listing` table, in Alembic migration `008_add_listing.py`
- The [`Listing`](./DATAMODEL_TECH.md#listing) section and the overview edges in the internal data model
- The LSA and LMA definitions in [Definitions](./DEFINITIONS.md), which the registry `name` must match (docs-consistency gate)
- A test client per role, in `keycloak/machine-clients.yaml` and `scripts/generate-keycloak-machine-clients.py`, with the credentials exported by the root `Makefile`
- End-to-end tests `tests/test_*_listings.py`, run by the `make test-<role>` targets and `scripts/run-tests.sh`
- The `listing` rows in `postgres/clean-testrun.sql` (test cleanup) and `postgres/count-app.sql`
