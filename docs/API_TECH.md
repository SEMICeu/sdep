<h1>API</h1>

This document describes the SDEP API.

<h2>Table of Contents</h2>

- [Principle](#principle)
- [Patterns](#patterns)
- [Domains](#domains)
- [Surface](#surface)
  - [Authentication](#authentication)
  - [Competent authority (CA)](#competent-authority-ca)
  - [Short-term rental platform (STR)](#short-term-rental-platform-str)
  - [Listing screening authority (LSA)](#listing-screening-authority-lsa)
  - [Listing monitoring authority (LMA)](#listing-monitoring-authority-lma)
  - [Activity monitoring authority (AMA)](#activity-monitoring-authority-ama)
  - [Statistics authority (STA)](#statistics-authority-sta)
  - [Common](#common)
- [Versioning](#versioning)
  - [Design](#design)
  - [Contract](#contract)
  - [Actual versions](#actual-versions)
  - [Actual versions diff](#actual-versions-diff)
  - [Operation ids](#operation-ids)
  - [Implementation (addition)](#implementation-addition)
  - [Implementation (deprecation)](#implementation-deprecation)
  - [Export](#export)
- [Filtering](#filtering)
  - [Areas](#areas)
  - [Listings](#listings)
  - [Activities](#activities)
  - [Reference data](#reference-data)
- [HTTP status codes](#http-status-codes)
  - [Success](#success)
  - [Client errors](#client-errors)
  - [Server errors](#server-errors)
  - [Error response body](#error-response-body)
- [OpenAPI vs Swagger UI](#openapi-vs-swagger-ui)
  - [OpenAPI](#openapi)
  - [Swagger UI](#swagger-ui)
  - [Are they interchangeable?](#are-they-interchangeable)
  - [Example](#example)
  - [Takeaways](#takeaways)
- [NLgov REST API Design Rules](#nlgov-rest-api-design-rules)
- [API gateway?](#api-gateway)
  - [Motivation](#motivation)
  - [When](#when)
  - [Conclusion](#conclusion)
- [Code structure](#code-structure)
  - [One sub-app per domain version](#one-sub-app-per-domain-version)
  - [Domain registry](#domain-registry)
  - [Sub-app factory](#sub-app-factory)
  - [Routers](#routers)
  - [Shared building blocks](#shared-building-blocks)
  - [OpenAPI document](#openapi-document)
  - [Adding a version](#adding-a-version)

## Principle

**Keep the API as simple and concise as possible.**

> REST APIs are one of the most common kinds of web interfaces available today. \
> Therefore, it's very important to design REST APIs properly so that we won't run into problems down the road. \
> Otherwise, we create problems for clients that use our APIs, which isn’t pleasant and detracts people from using our API. \
> If we don’t follow commonly accepted conventions, then we confuse the maintainers of the API and the clients that use them since it’s different from what everyone expects.

---

*<https://stackoverflow.blog/2020/03/02/best-practices-for-rest-api-design/>*

## Patterns

| #          | Decision                                                                                          | Motivation/example                                                                                                       |
| :--------- | :------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------- |
| **API 01** | Support OpenAPI 3.1.0                                                                             | Swagger 2.0 is legacy - <https://swagger.io/specification/>                                                              |
| **API 02** | All endpoints are self-explanatory/well-documented                                                |                                                                                                                          |
| **API 03** | Use noun instead of verbs                                                                         | Best practice, for example <https://logius-standaarden.github.io/API-Design-Rules/>                                      |
| **API 04** | Use plural nouns for collections and query parameters (with pagination) for filtering collections | Best practice, for example <https://learn.microsoft.com/en-sg/azure/architecture/best-practices/api-design/>             |
| **API 05** | Consistent datamodel                                                                              | Avoid code duplication, e.g. have unified `Activity`, `Listing`, `Area` and error responses                              |
| **API 06** | Consistent endpoints                                                                              | Collection endpoints, explicit "bulk" qualification where needed: `POST /ca/areas` vs. `POST /str/listings/bulk` **[1]** |
| **API 07** | Consistent pagination                                                                             | Have `offset` and `limit` for all endpoints with (potential) many records                                                |
| **API 08** | Syntax validation                                                                                 | Example: `postal code`                                                                                                   |
| **API 09** | Semantical validation                                                                             | Example: `begin timestamp < end timestamp`                                                                               |
| **API 10** | Integrity validation                                                                              | Example: can only submit activities or listings for existing areas that are regulated for that purpose **[2]**           |
| **API 11** | Bulk POST                                                                                         | Every write is a bulk write, up to 1000 items per batch **[1]**                                                          |
| **API 12** | Logical ordering => readability                                                                   | For POST, request and response follow the same ordering, extra data in response (e.g. `createdAt`) is moved to the end   |
| **API 13** | Essentiality                                                                                      | Example: in `/str/activities/bulk` and `/str/listings/bulk`, only `areaId`, but no `competentAuthorityId` **[3]**        |
| **API 14** | Essentiality/security                                                                             | Example: in POST activities, no need to include `platformId`                                                             |
| **API 15** | Consistent HTTP response codes                                                                    | See [HTTP status codes](#http-status-codes) below                                                                        |
| **API 16** | STR and CA: manage area change                                                                    | Areas may change over time, SDEP only administrates the changes and exposes the latest "truth"                           |
| **API 17** | Unified response format                                                                           | Example: `ActivityResponse` (for STR and CA), and one `ListingResponse` for all five reading audiences **[4]**           |

[1] `POST /str/activities/bulk`, `POST /str/listings/bulk`, `POST /lsa/listing-screenings/bulk` and `POST /str/listing-acknowledgements/bulk`.

[2] What an area is regulated for, see [Area](./AREA_FUNC.md#regulation).

[3] Wrong example, see GitHub issue [#95](https://github.com/SEMICeu/sdep/issues/95)

[3] Scope narrows **which** listings an audience sees, never which fields: no field is audience-confidential. Audience-only data would get its own schema.

## Domains

API-endpoints are exposed in the following domains:

- Authentication
- Competent authority (CA)
- Short-term rental platform (STR)
- Listing screening authority (LSA)
- Listing monitoring authority (LMA)
- Activity monitoring authority (AMA)
- Statistics authority (STA)
- Common (ping & health)

## Surface

### Authentication

- `POST /api/auth/v1/token` - OAuth 2.0 token endpoint

---

### Competent authority (CA)

**Areas** - specifics in [Area (technical)](./AREA_TECH.md)

**v1**

- `POST /api/ca/v1/areas` - Submit a single area (multipart/form-data: file + optional areaId, areaName)
- `GET /api/ca/v1/areas` - List own areas (pagination: offset, limit)
- `GET /api/ca/v1/areas/count` - Count own areas
- `GET /api/ca/v1/areas/{areaId}` - Download shapefile for own area
- `DELETE /api/ca/v1/areas/{areaId}` - Delete (deactivate) an own area

**v2 - unchanged**

Every `/api/ca/v1/areas...` path above is also served at `/api/ca/v2/areas...`, with the same request, response, and authorization. In both versions, `GET /areas` returns at most 1000 areas per call (`limit` defaults to 1000, the maximum).

---

**Listings (random checks)** - specifics in [Listing (technical)](./LISTING_TECH.md)

**v2 - new (alpha)**

- `GET /api/ca/v2/listings` - Query the acknowledged listings in the authority's own areas (fixed scope: `status` is `acknowledged`; pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, areaId, platformId, flags)
- `GET /api/ca/v2/listings/count` - Count acknowledged listings with optional filters (same filter set)

---

**Activities** - specifics in [Activity (technical)](./ACTIVITY_TECH.md)

**v1**

- `GET /api/ca/v1/activities` - Query rental activities with optional filters (pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, platformId, areaId; filters use AND semantics and are scoped to the authenticated CA; createdAt filters must be UTC)
- `GET /api/ca/v1/activities/count` - Count activities with optional filters (same filter set)

**v2 - unchanged**

- `GET /api/ca/v2/activities` - Same as v1
- `GET /api/ca/v2/activities/count` - Same as v1

---

**Platforms** - see [Reference data](#reference-data)

**v2 - new (alpha)**

- `/api/ca/v2/platforms...`: list and count - Look up the platforms that the `platformId` filter refers to

---

### Short-term rental platform (STR)

**Areas** - specifics in [Area (technical)](./AREA_TECH.md)

**v1**

- `GET /api/str/v1/areas` - List regulated areas (pagination: offset, limit)
- `GET /api/str/v1/areas/count` - Count areas
- `GET /api/str/v1/areas/{areaId}` - Download shapefile for area

**v2 - mandatory pagination**

- `GET /api/str/v2/areas` - List regulated areas, at most 1000 per call (pagination: offset, limit - limit defaults to 1000, the maximum)
- `GET /api/str/v2/areas/count` and `GET /api/str/v2/areas/{areaId}` - unchanged, mounted from v1

---

**Listings (random checks)** - specifics in [Listing (technical)](./LISTING_TECH.md)

**v2 - new (alpha)**

- `POST /api/str/v2/listings/bulk` - Submit up to 1000 randomly selected listings for screening (JSON body); a resubmitted `listingId` corrects the listing while it is `pending`, later states are refused per item with `conflict_error`; listings are rejected for areas that are regulated for activity only, per item with `regulation_error`
- `GET /api/str/v2/listings` - Query the platform's own flagged listings (fixed scope: `status` is `flagged`; pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, areaId, competentAuthorityId)
- `GET /api/str/v2/listings/count` - Count flagged listings with optional filters (same filter set)
- `POST /api/str/v2/listing-acknowledgements/bulk` - Acknowledge up to 1000 flagged listings (JSON body: `listingId` + `createdAt` version token); a token that is no longer current is refused per item with `conflict_error`

---

**Activities** - specifics in [Activity (technical)](./ACTIVITY_TECH.md)

**v1**

- `POST /api/str/v1/activities/bulk` - Submit up to 1000 activities in bulk (JSON body); `url` up to 128 and `fullAddress` up to 318 characters

**v2 - stricter and wider input**

- `POST /api/str/v2/activities/bulk` - As v1, plus: `url` up to 2048 and `fullAddress` up to 328 characters (widened); `startDatetime` and `endDatetime` must be UTC (offset `Z` or `+00:00`; other offsets, no offset and date-only values are rejected), and activities are rejected for areas that are regulated for listing only (`regulation` is `listing`), per item with `regulation_error`

---

### Listing screening authority (LSA)

**Listings (random checks)** - specifics in [Listing (technical)](./LISTING_TECH.md)

**v2 - new (alpha)**

Endpoints for the listing screening authority, an internal component that screens the submitted listings and raises flags:

- `GET /api/lsa/v2/listings` - Query the listings awaiting screening across all platforms (fixed scope: `status` is `pending`; pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, areaId, platformId, competentAuthorityId)
- `GET /api/lsa/v2/listings/count` - Count listings awaiting screening with optional filters (same filter set)
- `POST /api/lsa/v2/listing-screenings/bulk` - Submit up to 1000 screening results (JSON body: `platformId`, `listingId`, `createdAt` version token, `flags`); empty `flags` means `clear`, non-empty means `flagged`; a stale token or an acknowledged listing is refused per item with `conflict_error`

**Reference data** - `/api/lsa/v2/platforms...`, `/api/lsa/v2/competent-authorities...`, `/api/lsa/v2/areas...`: list and count, see [Reference data](#reference-data)

---

### Listing monitoring authority (LMA)

**Listings (random checks)** - specifics in [Listing (technical)](./LISTING_TECH.md)

**v2 - new (alpha)**

Read-only endpoints for the listing monitoring authority (no write endpoints registered; POST/PUT/PATCH/DELETE return 405):

- `GET /api/lma/v2/listings` - Query all current listings across all platforms and competent authorities, in every lifecycle status (pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, areaId, platformId, competentAuthorityId, flags, status)
- `GET /api/lma/v2/listings/count` - Count listings with optional filters (same filter set)

**Reference data** - `/api/lma/v2/platforms...`, `/api/lma/v2/competent-authorities...`, `/api/lma/v2/areas...`: list and count, see [Reference data](#reference-data)

---

### Activity monitoring authority (AMA)

**Activities** - specifics in [Activity (technical)](./ACTIVITY_TECH.md)

**v1**

Read-only endpoints for the activity monitoring authority, the STA v1 activity read behind the `sdep_ama` role (no write endpoints registered; POST/PUT/PATCH/DELETE return 405):

- `GET /api/ama/v1/activities` - Query rental activities across all competent authorities and platforms (pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, platformId, areaId, competentAuthorityId - AND semantics; createdAt filters must be UTC)
- `GET /api/ama/v1/activities/count` - Count activities with optional filters (same filter set)

**Reference data** - `/api/ama/v1/platforms...`, `/api/ama/v1/competent-authorities...`, `/api/ama/v1/areas...`: list and count, see [Reference data](#reference-data)

---

### Statistics authority (STA)

Read-only endpoints for the statistics authority (no write endpoints registered; POST/PUT/PATCH/DELETE return 405).

**Listings (random checks)** - specifics in [Listing (technical)](./LISTING_TECH.md)

**v2 - new (alpha)**

- `GET /api/sta/v2/listings` - Query all current listings across all platforms and competent authorities, in every lifecycle status (pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, areaId, platformId, competentAuthorityId, flags, status)
- `GET /api/sta/v2/listings/count` - Count listings with optional filters (same filter set)

---

**Activities** - specifics in [Activity (technical)](./ACTIVITY_TECH.md)

**v1**

- `GET /api/sta/v1/activities` - Query rental activities across all competent authorities and platforms (pagination: offset, limit - limit defaults to 1000, the maximum; filters: createdAtFrom, createdAtTo, platformId, areaId, competentAuthorityId - AND semantics; createdAt filters must be UTC; invalid functional IDs or non-UTC datetimes → 400)
- `GET /api/sta/v1/activities/count` - Count activities with optional filters (same filter set)

**v2 - unchanged**

Both `/api/sta/v1/activities...` paths above are also served at `/api/sta/v2/activities...`, with the same request, response, and authorization.

---

**Reference data** - `/api/sta/v1/platforms...`, `/api/sta/v1/competent-authorities...`, `/api/sta/v1/areas...`, `/api/sta/v2/platforms...`, `/api/sta/v2/competent-authorities...`, `/api/sta/v2/areas...`: list and count, see [Reference data](#reference-data)

---

### Common

- `GET /api/health` - Health check (unauthenticated, infrastructure use)
- `GET /api/ping` - Ping endpoint (authenticated, requires valid bearer token)

`GET /api/ping/docs` is a Swagger UI page for the ping endpoint, wired to the same
bearer-token scheme as the versioned domains, so a token can be entered through Authorize and
`/api/ping` exercised interactively. It is backed by `GET /api/ping/openapi.json`, a copy of
the common contract narrowed to that one path. The endpoints keep their own paths: mounting a
sub-app at `/api/ping` would make the endpoint itself redirect, so the docs routes are
registered on the common app instead.

`/api/health` has no docs page: it is declared with `include_in_schema=False` and so is
deliberately absent from the OpenAPI contract. The landing page at `/api/docs` groups both
under Common, linking the ping docs page and the health endpoint directly.

## Versioning

### Design

The API contract version is part of the URL path:

`/api/{domain}/v1/...`

A new version is introduced when:

- **A breaking change is required**, such as removing or renaming a field, changing its type, or changing its semantics.
- **New functionality is released early** while still subject to change, for example random checks/flagged listings in `str/v2`.

A domain typically exposes two active contracts, **N-1** and **N**, with a brief overlap during which **N+1** is introduced.

| Version | Status                | Purpose                                                                                                 |
| ------- | --------------------- | ------------------------------------------------------------------------------------------------------- |
| **N-1** | stable → deprecated   | Previous contract. Remains supported until its defined sunset date.                                     |
| **N**   | alpha → beta → stable | Current contract and primary version for consumers.                                                     |
| **N+1** | alpha → beta          | Next contract, introduced during a short transition period while N-1 is deprecated and awaiting sunset. |

This approach limits the number of concurrently supported contracts while giving consumers time to migrate between versions.

Lifecycle:

- **Alpha**:
  - New functionality is introduced and may change.
  - Intended for early feedback
  - It is deployed up to **PRE** only, controlled by `API_ALPHA_ENABLED` (to prevent test data from polluting PRD).
- **Beta**:
  - Feature-complete and changed only as needed to reach stable.
  - Intended for early integration and feedback.
  - It may be deployed to **PRD**.
- **Stable**:
  - Fully supported for production integrations.
  - Guarantees application [backward compatibility](./ARCHITECTURE_TECH.md#application-versioning) within the same API version.
  - Additive, backward-compatible read endpoints may also be introduced.
- **Deprecated**:
  - Once N becomes stable, N-1 may be deprecated and assigned a sunset date.

A short overlap is allowed:

- N+1 may enter alpha while N-1 is deprecated and awaiting sunset, temporarily exposing three contracts.
- After N-1 is removed, the version roles shift: N becomes N-1 and N+1 becomes N.

The endpoints exposed by each contract are listed in [Surface](#surface), and differences between consecutive versions are documented in [API version diff](API_DIFF_TECH.md).

---

### Contract

The version number identifies the **client contract**. Lifecycle status - `alpha`, `beta`, `stable`, or `deprecated` - is metadata about that contract and does not change its URL.

Promotion and demotion (deprecation) therefore changes only lifecycle metadata, not contract identity.

For example:

- STR v1 - stable (N-1)
- STR v2 - alpha (N)

When STR v2 is promoted to stable:

- **STR v2** remains available at `/v2`; existing clients continue using the same URL.
- **STR v1** may become deprecated and remain available until its sunset date.
- **STR v3** may start as alpha while STR v1 is still awaiting sunset.

This separation is deliberate. SDEP APIs are consumed across organizational boundaries, where clients may have independent release cycles, generated SDKs, regression tests, and change-management processes. If the contract itself has not changed, promoting it from beta to stable should not require consumers to change URLs, regenerate clients, or redeploy.

The URL path therefore represents the durable compatibility boundary:

- `/v1/...` → contract 1
- `/v2/...` → contract 2
- `/v3/...` → contract 3

Lifecycle status describes the maturity and support level of a contract; it is not part of the contract's identity.

This contract-oriented model is also used in public-sector and regulated API ecosystems:

- The [Dutch Government API Design Rules](https://logius-standaarden.github.io/API-Design-Rules/#versioning) place the major API version in the URI.
- The [Berlin Group / NextGenPSD2](https://www.berlin-group.org/nextgenpsd2-downloads) Implementation Guidelines similarly use versioned interface paths such as `/v1/{service}`, while specification releases are managed separately.

Consequences:

- **No migration on promotion:** `/v2` remains `/v2` when it moves from beta to stable.
- **Client-controlled migration:** moving from `/v1` to `/v2` means explicitly adopting a different contract.
- **One OpenAPI document per contract:** clients generate against the exact contract they integrate with.
- **No mixed-stability contract:** alpha, beta, and stable operations are not combined within one contract using flags such as `x-stability`.

---

### Actual versions

| Domain | Version | Status | Notes                                                                                  |
| ------ | ------- | ------ | -------------------------------------------------------------------------------------- |
| auth   | v1      | stable | OAuth 2.0 token endpoint (client credentials)                                          |
| ca     | v1      | stable | Areas + activities (no filters)                                                        |
| ca     | v2      | alpha  | Activity filters, limit 1000, acknowledged listings (random checks), platforms         |
| str    | v1      | stable | Areas (read-only) + bulk activity submission                                           |
| str    | v2      | alpha  | UTC-only timestamps, regulation check, limit 1000, listings (random checks)            |
| lsa    | v2      | alpha  | Listing screening authority: pending listings + bulk screening results, reference data |
| lma    | v2      | alpha  | Read-only listing monitoring API, every lifecycle status, reference data               |
| ama    | v1      | stable | Read-only activity monitoring API (the STA read, own role), reference data             |
| sta    | v1      | stable | Read-only statistics API: activities, reference data                                   |
| sta    | v2      | alpha  | Read-only statistics API: activities, listings (random checks), reference data         |

---

### Actual versions diff

The differences between consecutive API versions are generated from the committed OpenAPI snapshots and published in [API version diff](API_DIFF_TECH.md). The document is regenerated with `make api-diff-update` from `backend/` and is gated by the backend test suite, so it cannot drift from the contract.

In short: CA v2 is CA v1 plus documented field maximums on the activity response, the acknowledged-listings read and the platform reads. STR v2 is STR v1 with UTC-only timestamps, the activity regulation check, a `limit` that defaults to 1000, and the listing endpoints (random checks). STA v2 is STA v1 plus the listing endpoints (random checks). No changes to the paths or authorization shared with the previous version. See [Listings](#listings) and [Activities](#activities) for the filter parameters.

Each version also carries its own cross-version note in the OpenAPI `info.description`, so it is visible at the top of that version's Swagger UI without leaving the API.

---

### Operation ids

Every operation carries an explicit `operationId`, which client code generators turn into a method name.

- Operations that a new version redefines carry a `VN` suffix from v2 onward, for example `getActivityByCompetentAuthorityV2` and `countActivitiesV2`. This keeps the ids unique across the versions that co-exist
- Operations that a new version mounts unchanged keep a single id across versions. Four area operations (`postArea`, `countOwnAreas`, `getOwnArea`, `deleteOwnArea`) are shared by CA v1 and CA v2 and are therefore not suffixed; `getOwnAreas` is redefined in v2 (pagination default) and becomes `getOwnAreasV2`. STR v2 likewise redefines `getAreasV2` and `postActivitiesBulkV2` and shares `countAreas` and `getArea`
- Operations first introduced in a later version carry that version's suffix as well (`postListingsBulkV2`, `getListingsV2`, `getListingsByCompetentAuthorityV2`), so a later version that redefines them cannot clash

A consequence is that the generated version diff reports an `operationId` change for the redefined operations. That is intended, not drift.

---

### Implementation (addition)

Each domain is exposed as one or more independently-versioned FastAPI sub-applications,
mounted side by side (e.g. `/api/ca/v1`, `/api/ca/v2`). A new version is additive:
existing versions stay byte-compatible.

Shared vs. version-specific code (CA domain as example):

- Shared (one source of truth, used by every version):
  - `app_factory.py` - `create_domain_app(domain, routers)` builds the sub-app (title,
    common 500/503 responses, OpenAPI, exception handlers, bearer-token override,
    `openapi.json` route)
  - `domain_registry.py` - per-version metadata (label, name: the acronym spelled out as
    in `DEFINITIONS.md`, title, description, status, scope: EU-harmonized or
    country-specific, which groups the landing page) and
    the cross-version links that render the "Changes from ..." / "Superseded by ..." note
    into the OpenAPI description
  - `common/listing_handlers.py`, `common/listing_filters.py`, `common/listing_examples.py` - the listing endpoint business logic: one read handler with a fixed scope per audience, shared query-parameter types, shared examples
  - `common/activity_handlers.py` - the activity endpoint business logic (list/count)
  - `common/bulk_json.py` - the HTTP status mapping of every bulk result (201, 200, 422)
  - `common/pagination.py` - the shared offset/limit query dependency
  - `domains/ca/routers/areas.py` - the areas endpoints, mounted into every version
  - `common/activity_examples.py` - response examples and error-response constants,
    imported by every version
  - `schemas/activity.py`, `services/activity.py`, `crud/activity.py` - the data
    layers; newer behavior (e.g. filters) is added here and gated by the routers
- Version-specific (one small file per version):
  - `routers/activities_vN.py` - the route declarations and any version-only query
    parameters (e.g. v2 adds the `filter*` inputs via an `activity_filters()` dependency)
  - `vN.py` - a one-line call to the factory wiring the version's router

Adding a version is therefore cheap: define a new `activities_vN.py`, a one-line
`vN.py`, mount it in `main.py`, register the version in `domain_registry.py`, and add its
`/docs` + `/openapi.json` paths to the audit skip-list and CSP allowlist.

The contract of every version is frozen in `backend/tests/api/fixtures/`, and the
difference between consecutive versions is generated into [API version diff](API_DIFF_TECH.md).
Both are gated by the backend test suite: change an endpoint and the suite fails until
`make api-snapshot-update` and `make api-diff-update` have been run and the diff reviewed.

---

### Implementation (deprecation)

Deprecation retires an API version: it stays available and unchanged, but it is closed for new integrations and has an end date.

**Lifecycle**

| Step | Old version      | New version       | Trigger                                           |
| ---- | ---------------- | ----------------- | ------------------------------------------------- |
| 1    | stable (N-1)     | alpha or beta (N) | The new version is released alongside the old one |
| 2    | stable (N-1)     | stable (N)        | The new version is promoted                       |
| 3    | deprecated (N-1) | stable (N)        | A sunset date is set and announced                |
| 4    | removed          | stable (N)        | The sunset date has passed                        |

Rules:

- A version is only deprecated once its successor is stable. Clients are never asked to migrate onto a contract that may still change.
- A next version (N+1, alpha) may start from step 3 on, the short overlap in [Design](#design). Once the old version is removed (step 4), the table starts again with N as the old version and N+1 as the new one.
- A deprecated version keeps its contract. Deprecation announces intent, it does not change behavior.
- Proposal, requires discussion in the technical working group: the deprecation period is at least **six months** between the `Sunset` announcement and removal, the transition period the Dutch government API guidance recommends (NLgov REST API Design Rules `/core/transition-period`). The `Sunset` header carries that fixed date. Measured use may extend the period, never shorten it: the audit log records the request path, so it shows how much a version is still called.
- Removal is a separate, later step.

**Signals**

All signals derive from the version's status in the domain registry (`backend/app/api/domain_registry.py`), so deprecating a version is a metadata change and not an endpoint change:

| Signal                                              | Where                                            | Audience                                       |
| --------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------- |
| Status badge and `Status: deprecated.` note         | Docs landing page and OpenAPI `info.description` | People reading the documentation               |
| `deprecated: true` per operation                    | The version's `openapi.json`                     | Client generators, Swagger UI                  |
| `Deprecation`, `Sunset` and `Link` response headers | Every response of the deprecated version         | Running clients, without reading documentation |

Remarks:

- The operation flag is applied per sub-application while the OpenAPI document is generated, never on a router. Routers are shared between versions (e.g. the CA area endpoints, see [Operation Ids](#operation-ids)), so a flag on a router would deprecate the successor as well.
- `Deprecation` carries the date the version became deprecated ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745.html)), `Sunset` the date it is removed ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594.html)), and `Link` points at the successor with `rel="successor-version"` ([RFC 5829](https://www.rfc-editor.org/rfc/rfc5829.html)).
- The [Actual versions diff](#actual-versions-diff) reports the flag flip between two versions, so a deprecation shows up in the generated version comparison.

**Removal**

- The sub-application is unmounted and its version-specific routers are deleted. Shared code stays for the remaining versions.
- The removed paths then return a routing-level [404](#client-errors). No separate "gone" handling is added.
- The version also leaves the [Actual versions](#actual-versions) table, the audit skip-list, and the CSP allowlist.

---

### Export

One-off API PDF export for specific API versions:

- [API auth_v1 pdf](./sdep_openapi_auth_v1.pdf)
- [API ca_v1 pdf](./sdep_openapi_ca_v1.pdf)
- [API str_v1 pdf](./sdep_openapi_str_v1.pdf)

> Disclaimer: These PDFs were generated as part of the v1 freeze on 28 April 2026. While the /v1 API is frozen, implementation details may still differ in certain cases (see the [changelog](../CHANGELOG.md) for updates).

## Filtering

### Areas

The area endpoints take **no query filters**, only pagination. The scope is fixed: a competent authority reads its own areas, a platform reads every regulated area, because it needs all of them to decide what to submit. The read-only audiences (AMA, STA, LMA, LSA) read every area too, see [Reference data](#reference-data).

`GET /areas` is unlimited by default in STR v1. In CA v1 and from v2 on it returns at most 1000 records per request (`limit` defaults to 1000, the maximum); use `offset` together with `GET /areas/count`.

---

### Listings

Every audience reads the same `GET /listings` and `GET /listings/count`; the router fixes the scope (which listings), the query string narrows it further. A filter that an audience may not use is simply not declared in its OpenAPI document.

| Audience | Fixed scope                           | `createdAtFrom` / `createdAtTo` | `areaId` | `platformId` | `competentAuthorityId` | `flags` | `status` |
| -------- | ------------------------------------- | ------------------------------- | -------- | ------------ | ---------------------- | ------- | -------- |
| STR v2   | own platform, `status` is `flagged`   | yes                             | yes      | -            | yes                    | -       | -        |
| LSA v2   | all platforms, `status` is `pending`  | yes                             | yes      | yes          | yes                    | -       | -        |
| CA v2    | own areas, `status` is `acknowledged` | yes                             | yes      | yes          | -                      | yes     | -        |
| LMA v2   | all platforms, every status           | yes                             | yes      | yes          | yes                    | yes     | yes      |
| STA v2   | all platforms, every status           | yes                             | yes      | yes          | yes                    | yes     | yes      |

- `createdAtFrom` / `createdAtTo`: inclusive bounds on `createdAt` (ISO 8601, UTC, otherwise HTTP 400)
- `areaId`, `platformId`, `competentAuthorityId`: exact match on a functional ID (invalid format: HTTP 400)
- `flags`: comma-separated flag codes, for example `flags=UDS,EXP`; a listing matches when it carries any of them (unknown code: HTTP 400)
- `status`: one lifecycle status (`pending`, `clear`, `flagged`, `acknowledged`)

All provided filters are combined with AND semantics. `GET /listings` returns at most 1000 records per request (`limit` defaults to 1000, the maximum); use `offset` together with `GET /listings/count` to page through larger result sets.

---

### Activities

`GET /activities` and `GET /activities/count` are served by five domain versions. The router fixes the scope; the query string narrows it further. A filter that a domain may not use is simply not declared in its OpenAPI document.

| Domain | Fixed scope                    | `createdAtFrom` / `createdAtTo` | `areaId` | `platformId` | `competentAuthorityId` |
| ------ | ------------------------------ | ------------------------------- | -------- | ------------ | ---------------------- |
| CA v1  | own areas                      | -                               | -        | -            | -                      |
| CA v2  | own areas                      | yes                             | yes      | yes          | -                      |
| STA v1 | all authorities, all platforms | yes                             | yes      | yes          | yes                    |
| STA v2 | all authorities, all platforms | yes                             | yes      | yes          | yes                    |
| AMA v1 | all authorities, all platforms | yes                             | yes      | yes          | yes                    |

- `createdAtFrom` / `createdAtTo`: inclusive bounds on `createdAt` (ISO 8601, UTC; no offset or another offset returns HTTP 400)
- `areaId`, `platformId`, `competentAuthorityId`: exact match on a functional ID (invalid format: HTTP 400)

All provided filters are combined with AND semantics; omitting one means no constraint on that dimension. If OR semantics are needed, call the endpoint per value and combine client-side.

The CA `GET /activities` (v1 and v2) returns at most 1000 records per request (`limit` defaults to 1000, the maximum); use `offset` together with `GET /activities/count` to page through larger result sets.

STA and AMA register no write endpoints: POST, PUT, PATCH and DELETE return HTTP 405. STA requires `sdep_sta`, AMA requires `sdep_ama`, both with `sdep_read`.

---

### Reference data

Rule: every ID that an API filters on can be looked up in that same API. So the audiences that filter on `platformId`, `competentAuthorityId` or `areaId` get read-only lookup endpoints:

| Endpoint                           | Response                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------- |
| `GET /platforms`                   | `platforms`: `platformId`, `platformName`, `createdAt`                                |
| `GET /platforms/count`             | `count`                                                                               |
| `GET /competent-authorities`       | `competentAuthorities`: `competentAuthorityId`, `competentAuthorityName`, `createdAt` |
| `GET /competent-authorities/count` | `count`                                                                               |
| `GET /areas`                       | `areas`, same as STR (includes `competentAuthorityId`)                                |
| `GET /areas/count`                 | `count`                                                                               |

| Domain         | Platforms | Competent authorities | Areas                                           |
| -------------- | --------- | --------------------- | ----------------------------------------------- |
| AMA v1         | yes       | yes                   | yes                                             |
| STA v1, v2     | yes       | yes                   | yes                                             |
| LMA v2, LSA v2 | yes       | yes                   | yes                                             |
| CA v2          | yes       | - (the caller itself) | own areas, see [CA](#competent-authority-ca)    |
| STR v1, v2     | -         | -                     | yes, see [STR](#short-term-rental-platform-str) |

- Current versions only: an ended platform, authority or area is not listed
- No read by ID: the list item carries every field. The area shapefile download (`GET /areas/{areaId}`) stays with STR, which submits per area, and CA, which owns the areas
- Lists return at most 1000 records per request (`limit` defaults to 1000, the maximum)
- The private `client_id` is never exposed
- Code: one router factory per resource in `app/api/common/reference_routers.py`

## HTTP status codes

### Success

| HTTP Status | Meaning    | When                                                                                                |
| ----------- | ---------- | --------------------------------------------------------------------------------------------------- |
| 200         | OK         | GET request completed successfully; bulk POST with partial success (created multiple new resources) |
| 201         | Created    | POST request created a single new resource                                                          |
| 204         | No Content | DELETE request completed successfully (e.g. deactivate area)                                        |

---

### Client errors

| HTTP Status | Meaning               | When                                                                                                                                                                              |
| ----------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 400         | Bad Request           | Invalid query parameters on a GET request (e.g. `offset=-1` or `limit=abc`), or missing client credentials                                                                        |
| 401         | Unauthorized          | Missing, invalid, or expired authentication token; missing required token claims (`client_id`, `client_name`)                                                                     |
| 403         | Forbidden             | Authenticated but missing a required role (`sdep_ca`, `sdep_str`, `sdep_lsa`, `sdep_lma`, `sdep_ama`, `sdep_sta`, `sdep_read`, `sdep_write`)                                      |
| 404         | Not Found             | Requested resource does not exist, is unavailable, or has been deleted                                                                                                            |
| 409         | Conflict              | Duplicate resource (unique constraint violation)                                                                                                                                  |
| 413         | Payload Too Large     | Upload exceeds the per-endpoint size limit (e.g. `POST /api/ca/v1/areas` rejects requests whose `Content-Length` exceeds the 1 MiB file-size cap plus a small multipart envelope) |
| 422         | Unprocessable Content | Invalid request body on a POST request (e.g. missing required field) or business rule violation (e.g. start time > end time)                                                      |

---

### Server errors

| HTTP Status | Meaning               | When                                                                     |
| ----------- | --------------------- | ------------------------------------------------------------------------ |
| 500         | Internal Server Error | Unexpected condition that prevented fulfilling the request (catch-all)   |
| 503         | Service Unavailable   | Database or authorization server (e.g. Keycloak) temporarily unavailable |

For the mapping between application exceptions and HTTP status codes, see [Exceptions](ARCHITECTURE_TECH.md#exceptions) in the Technical Architecture document.

---

### Error response body

Application errors (validation, authorization, business rules, and similar) use the standardized `Error.Response` schema (`ErrorResponse` in code, see `backend/app/schemas/error.py`): a JSON object whose `detail` is a list of error objects, each with `msg`, `type`, and an optional `loc`.

A few framework-level responses are produced by FastAPI's router before a request reaches application code, and these use FastAPI's default body shape instead, where `detail` is a plain string rather than the standardized list:

- 405 Method Not Allowed (e.g. a write method on the read-only STA API)
- Routing-level 404 Not Found (a path that matches no registered route)

This is intentional and behaves identically across the CA, STR, and STA APIs.

## OpenAPI vs Swagger UI

### OpenAPI

The **[OpenAPI Specification](https://www.openapis.org/)** (formerly *Swagger Specification*) is a language-agnostic standard (currently 3.1.0) for describing HTTP APIs.

- A single document enumerates every endpoint, its request parameters and body, its response shapes per HTTP status code, its authentication scheme, and the data types (`components.schemas`) those endpoints consume and produce
- With constraints like lengths, patterns, enums, required fields, and examples

SDEP exposes this document per domain at:

```
GET /api/auth/v1/openapi.json

GET /api/ca/v1/openapi.json
GET /api/ca/v2/openapi.json

GET /api/str/v1/openapi.json
GET /api/str/v2/openapi.json

Etc.
```

The OpenAPI Specification is the **authoritative, machine-readable contract** of the API.

- FastAPI generates it automatically from the Pydantic schemas and route definitions in the code, so it is always in sync with the running backend
- It is what client code generators (e.g. [openapi-generator](https://openapi-generator.tech/), [openapi-typescript](https://github.com/openapi-ts/openapi-typescript)), contract-test tools, mock servers, schema registries, and spec-diff tools consume

Key properties:

- **Versioned, machine-readable** - diffable in git, consumable by tooling.
- **Single source of truth** - endpoints, schemas, and examples live in one document.
- **Reusable components** - named schemas (`#/components/schemas/...`) are referenced via `$ref` so the same type can appear in many places without duplication.

---

### Swagger UI

**[Swagger UI](https://swagger.io/tools/swagger-ui/)** is an interactive, browser-based **renderer** of an OpenAPI document.

- It is *not* a separate specification or a separate source of truth
- It reads the same `openapi.json` and presents it as a navigable page with collapsible endpoints, schema trees, and a built-in "Try it out" form that submits live requests against the running backend

SDEP serves it per domain at:

```
GET /api/auth/v1/docs

GET /api/ca/v1/docs
GET /api/ca/v2/docs

GET /api/str/v1/docs
GET /api/str/v2/docs

Etc.
```

A landing page at `GET /api/docs` links to all domain docs, grouped in two levels:

- By group, with its major version: v1 (authentication), v1 (activities), v2 (listings)
- Within a group, by scope: EU-harmonized (Auth, STR) and country-specific (AMA, CA, LMA, LSA, STA); a scope without domains is left out

Within a scope the domains are sorted alphabetically, and every row shows the acronym
spelled out (right-aligned), as defined in [Definitions](./DEFINITIONS.md). The groups
and their headings are `API_GROUPS` in `domain_registry.py`.

Swagger UI's audience is humans: developers exploring the API, integrators drafting their first request, reviewers sanity-checking a change.

To keep that audience oriented, Swagger UI **summarizes where the raw spec would overwhelm** - e.g. it may label a field as `array<object>` even when the spec contains a named `$ref` to a typed component. The typed detail is still reachable (one click deeper), but the top-level label is deliberately compact.

---

### Are they interchangeable?

The two are not interchangeable:

- When a schema is non-trivial (arrays of typed objects, composed `$ref`s, polymorphism), Swagger UI summarizes while the raw JSON retains the full detail
- Always treat `openapi.json` as the source of truth

---

### Example

`POST /str/activities/bulk`

The bulk endpoint's request body is `ActivityBulkRequest`, whose `activities` field is an array of `ActivityRequest`. The contract expresses this precisely; Swagger UI renders it in a more compact way.

**1. Swagger UI (Schema tab)**

Swagger UI shows the request body as `ActivityBulkRequest (object)`. The `activities*` property is labeled:

```
activities*   array<object>   [1, 1000] items
```

- i.e. Swagger UI's item-type label is the generic word `object`, not `ActivityRequest`. The typed structure is still there, just one level deeper: expanding `Items` reveals a nested `object` block with every `ActivityRequest` property (`activityId`, `activityName`, `areaId`, `address`, `registrationNumber`, `numberOfGuests`, `countryOfGuests`, `temporal`, …) including their constraints, examples, and descriptions. So Swagger UI does render the full schema; it just does not surface the referenced **type name** at the array level.

**2. openapi.json - request body reference**

In the raw document, the endpoint body points at a named component:

```json
"/str/activities/bulk": {
  "post": {
    "requestBody": {
      "content": {
        "application/json": {
          "schema": { "$ref": "#/components/schemas/ActivityBulkRequest" }
        }
      }
    }
  }
}
```

**3. openapi.json - `ActivityBulkRequest` definition**

The wrapper references another named component for the item type:

```json
"ActivityBulkRequest": {
  "type": "object",
  "required": ["activities"],
  "title": "Activity.BulkRequest",
  "properties": {
    "activities": {
      "type": "array",
      "minItems": 1,
      "maxItems": 1000,
      "items": { "$ref": "#/components/schemas/ActivityRequest" }
    }
  }
}
```

**4. openapi.json - `ActivityRequest` definition**

`ActivityRequest` is a top-level, reusable component with every property and its constraints spelled out:

```json
"ActivityRequest": {
  "type": "object",
  "title": "Activity.Request",
  "required": ["areaId", "url", "address", "registrationNumber",
               "numberOfGuests", "countryOfGuests", "temporal"],
  "properties": {
    "activityId": {
      "anyOf": [
        { "type": "string", "minLength": 1, "maxLength": 64,
          "pattern": "^[A-Za-z0-9-]+$" },
        { "type": "null" }
      ],
      "examples": ["550e8400-e29b-41d4-a716-446655440000"]
    },
    "activityName": { "anyOf": [ { "type": "string", "maxLength": 64 },
                                  { "type": "null" } ] }
    /* …remaining fields… */
  }
}
```

---

### Takeaways

- **Typing is explicit in `openapi.json`**, via chained `$ref`s: the endpoint → `ActivityBulkRequest` → `ActivityRequest`. Client code generators, contract-test tools, and spec-diff tools will pick this up and produce typed models.
- **Swagger UI's `array<object>` label is cosmetic**, not a loss of schema detail. The underlying typed item schema is still available one click deeper under *Items*.
- **Consume `openapi.json` for machine workflows** (code generation, conformance tests, contract diffs). **Use Swagger UI for exploratory human reading** and manual request submission.
- **When a spec question arises, check `openapi.json` first.** If a type appears to be "just an object" in Swagger UI, it almost always has a named component behind it - follow the `$ref`.

## NLgov REST API Design Rules

Compliance check against the [NLgov REST API Design Rules](https://gitdocumentatie.logius.nl/publicatie/api/adr/2.2.0/) 2.2.0 (definitive, 2 June 2026), conform the Dutch government [Forum Standaardisatie](https://www.forumstandaardisatie.nl/open-standaarden/rest-api-design-rules).

Checked on 24 September 2026:

| Compliance    | Meaning                                             | #      |
| ------------- | --------------------------------------------------- | ------ |
| **OK**        | The rule holds                                      | **27** |
| **Roadmap**   | The rule does not hold yet, a fix can be considered | **3**  |
| **Deviation** | The rule does not hold on purpose > **explain**     | **4**  |
| **N/A**       | The rule does not apply                             | **2**  |
| Total         |                                                     | 36     |

Verdict per rule, with some \[footnotes\]:

| Rule                                     | Verdict   | Evidence                                                                                                                                         |
| ---------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/core/naming-resources`                 | OK        | Nouns: `areas`, `activities`, `listings`, `listing-screenings`, `listing-acknowledgements`, `token` **[1]**                                      |
| `/core/naming-collections`               | OK        | Every collection is plural                                                                                                                       |
| `/core/interface-language`               | Deviation | English **[2]**                                                                                                                                  |
| `/core/no-trailing-slash`                | OK        | A trailing slash returns 404; the frozen v1 contracts (Auth, CA, STR) keep their 307 redirect **[3]**; backend test                              |
| `/core/path-segments-kebab-case`         | OK        | `listing-screenings`, `listing-acknowledgements`                                                                                                 |
| `/core/query-keys-camel-case`            | OK        | `createdAtFrom`, `platformId`, `areaId`                                                                                                          |
| `/core/hide-implementation`              | OK        | No `Server` header, functional IDs instead of database keys, generic error bodies                                                                |
| `/core/date-time/format`                 | OK        | ISO 8601 throughout                                                                                                                              |
| `/core/date-time/timezone`               | Deviation | Responses are UTC; requests: STR v1 accepts any offset, STR v2 accepts UTC only (`Z` or `+00:00`) **[4]**                                        |
| `/core/date-time/date-omit-time-portion` | OK        | Date-only fields are dates                                                                                                                       |
| `/core/http-methods`                     | OK        | `GET`, `POST`, `DELETE` only                                                                                                                     |
| `/core/http-safety`                      | OK        | `GET` safe; `DELETE /areas/{areaId}` idempotent (a repeat returns 404); `POST .../bulk` not idempotent by design, see [Patterns](#patterns)      |
| `/core/http-response-code`               | OK        | [HTTP status codes](#http-status-codes)                                                                                                          |
| `/core/stateless`                        | OK        | Bearer token per request, no server-side session                                                                                                 |
| `/core/nested-child`                     | OK        | `/areas/{areaId}`; listings and activities are top-level, scoped by the token, no parent in the URI                                              |
| `/core/resource-operations`              | OK        | Operations are sub-resources: `/bulk`, `/count`                                                                                                  |
| `/core/error-handling/problem-details`   | Roadmap   | Error bodies are `{"detail": [...]}` with `application/json`, see [Error response body](#error-response-body) **[5]**                            |
| `/core/error-handling/invalid-input`     | Roadmap   | Invalid query parameters return 400, invalid request bodies 422, see [Client errors](#client-errors) **[5]**                                     |
| `/core/error-handling/all-errors`        | OK        | Validation returns every error at once; bulk endpoints report per item                                                                           |
| `/core/doc-openapi`                      | OK        | OpenAPI 3.1, one document per version                                                                                                            |
| `/core/doc-openapi-contact`              | OK        | `info.contact` (`name`, `url`, `email`) in every document, from settings `API_CONTACT_*`; also the landing-page footer                           |
| `/core/doc-language`                     | Deviation | English **[2]**                                                                                                                                  |
| `/core/publish-openapi`                  | Roadmap   | Published at `/api/{domain}/v{N}/openapi.json` without login, but other websites cannot read it yet **[6]**                                      |
| `/core/deprecation-schedule`             | OK        | [Implementation (deprecation)](#implementation-deprecation): badge, `deprecated: true`, `Deprecation`/`Sunset`/`Link` headers; not yet exercised |
| `/core/transition-period`                | OK        | Proposal: at least six months between the `Sunset` announcement and removal; measured use may extend it, never shorten it                        |
| `/core/uri-version`                      | OK        | `servers[].url` is `/api/{domain}/v{N}` (major only, `v` prefix); backend test on the served document                                            |
| `/core/changelog`                        | OK        | [CHANGELOG.md](../CHANGELOG.md) per release, [API version diff](API_DIFF_TECH.md) per version pair                                               |
| `/core/semver`                           | OK        | Contract major in the path; `info.version` and `API-Version` carry the release as `major.minor.patch` **[7]**                                    |
| `/core/version-header`                   | OK        | `API-Version: <major.minor.patch>` on every response, errors and unversioned paths included; backend test                                        |
| `/core/transport/tls`                    | OK        | TLS terminates at the ingress (deployment); the application adds HSTS                                                                            |
| `/core/transport/no-sensitive-uris`      | OK        | Credentials travel in headers and bodies; URIs carry functional IDs only                                                                         |
| `/core/transport/security-headers`       | OK        | All mandatory headers, see [Security headers](./SECURITY.md#security-headers); `Access-Control-Allow-Origin` deliberately absent **[6]**         |
| `/core/transport/cors`                   | OK        | No cross-origin access is granted **[6]**                                                                                                        |
| `/core/modules/geospatial`               | Deviation | Zipped shapefile, see [Areas](./AREA_FUNC.md) **[8]**                                                                                            |
| `/core/modules/signing`                  | N/A       | No application-level payload signing; integrity comes from TLS                                                                                   |
| `/core/modules/encryption`               | N/A       | No application-level payload encryption; confidentiality comes from TLS                                                                          |

[1] `health` and `ping` are infrastructure endpoints, not resources.

[2] SHOULD rule, English on purpose:

- The STR API is EU-harmonized: Regulation (EU) 2024/1028 and its data model are English
- The reference implementation is used by other Member States; a Dutch interface or documentation set would split one contract into two vocabularies
- The rule allows an official English glossary; the regulation is that glossary

[3] OK, because every contract after v1 returns 404 and no redirect: CA and STR v2, and all other domains. The v1 contracts were released with the redirect; keeping it means no stable client breaks. Auth has no later version yet, so Auth v1 still redirects. The exemption is a per-version flag in the domain registry, checked by the backend test suite.

[4] The rule asks to accept any offset; STR v2 accepts UTC only, on purpose (see [Surface](#surface)):

- Timestamps without an offset, or with mixed offsets in one batch, cannot be misread
- The database stores UTC, and v1 once crashed on a start without an offset and an end with one

[5] The rule asks for a different error format:

- Error bodies in the RFC 9457 format (`application/problem+json`)
- Status 400 instead of 422 for an invalid request body
- Both change what every client reads, so the fix can only come in a new contract version, never in a released one

[6] SDEP sends no CORS headers at all, so a browser blocks every call from another website:

- This is the strictest setting, on purpose: the API has machine clients only, and Swagger UI runs on the same website
- `/core/publish-openapi` asks one exception: `openapi.json` should send `Access-Control-Allow-Origin: *`, so browser tools on other websites can read the API description
- Fix: add that header on `openapi.json` only; the rest of the API keeps the strict setting
- The policy is described in [Security](./SECURITY.md#security-headers)

[7] The release version is the image tag (`0.0.0-dev` locally). The environment (DTAP) is a separate landing-page badge, so the version string stays parseable.

[8] MUST rule, shapefile on purpose:

- The zipped shapefile is the format the EU-harmonized STR API prescribes for competent authorities, not the NLgov geospatial module (GeoJSON, OGC API Features)
- Converting on the edge would add a second geometry format to one contract and move the source of truth away from what the authorities publish

## API gateway?

For production use in your own country, the utilization of a separate API gateway can be considered (on top of the SDEP API).

Within **SDEP-NL**, a dedicated API gateway is currently **not** used. This is a deliberate choice based on how the platform is designed and operated. Only when specific edge-control requirements arise that cannot be handled by the existing ingress/reverse proxy setup, an additional gateway could be introduced.

---

### Motivation

In context of SDEP-NL:

- **SDEP-NL already provides clear API boundaries** \
  The SDEP API itself acts as a functional gateway for data exchange, with well-defined domains (`str` vs `ca`), the OAuth 2.0 Client Credentials flow, and strict role separation.

- **Workload is primarily transactional, not cache-driven** \
  Typical interactions (e.g. `POST /str/activities/bulk`, area upload/download) are write-heavy or data-exchange oriented, limiting the value of traditional API gateway features like response caching.

- **Existing edge setup is sufficient and controlled** \
  A hardened edge (ingress/reverse proxy + TLS termination) already provides the necessary entrypoint security and routing without introducing additional layers.

- **Operational simplicity is a key design principle** \
  Avoiding an extra gateway reduces:

  - Latency in the request path
  - Duplication of security and routing policies
  - Risk of configuration drift
  - An additional operational and failure domain

- **Authorization is intentionally handled at the right layers** \
  Identity and access control are enforced via the identity provider and the application itself, aligning with SDEP’s architecture rather than shifting logic to an external gateway.

---

### When

Introducing a gateway could become relevant when concrete needs arise, such as:

1. Platform-scale **rate limiting or quota management per client**
2. **Centralized security/policy enforcement** across multiple backend services (JWT claim rules, IP allowlists, mTLS, schema checks)
3. Need for **API product capabilities** (developer portal, client onboarding, usage analytics)
4. **Multi-service backend exposure** with a single stable external contract

---

### Conclusion

SDEP-NL prioritizes a **simple, robust edge architecture**. A dedicated API gateway should only be introduced when clear non-functional requirements outweigh the added complexity.

## Code structure

This section describes the **generic** API code setup: the parts every domain and every
version share. The layered architecture behind it (API, schemas, services, CRUD, models)
is in [Architecture](./ARCHITECTURE_TECH.md#backend); what each listing and activity
endpoint does is in [Listing](./LISTING_TECH.md) and [Activity](./ACTIVITY_TECH.md).

---

### One sub-app per domain version

Every domain version is its own FastAPI application, mounted on the root app
(`app/main.py`, `DOMAIN_APPS`; alpha versions only when `API_ALPHA_ENABLED` is on):

```text
app = FastAPI(lifespan=lifespan, redirect_slashes=False)   # root app, no routes of its own
  /api/auth/v1  -> app_auth_v1                             # app/api/domains/auth/v1.py
  /api/ca/v1    -> app_ca_v1                               # app/api/domains/ca/v1.py
  /api/ca/v2    -> app_ca_v2
  /api/str/v1   -> app_str_v1
  ...
  /api          -> app_common                              # mounted last, broadest path
```

Why a sub-app and not one app with version prefixes:

- Each version gets its own OpenAPI document and its own Swagger UI, so a client sees one contract, not all of them
- A frozen version stays frozen: its routers are not touched when the next version changes
- Mount order matters only for `app_common`, which is mounted last because `/api` covers every other path

---

### Domain registry

`app/api/domain_registry.py` is the **single source of truth** for what a domain version
is. One frozen `ApiDomain` dataclass per version, and `API_DOMAINS` holds them all.

| Field                                   | What it drives                                                                           |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| `label`, `name`                         | Docs landing page row, and the acronym spelled out                                       |
| `root_path`                             | Mount path in `main.py`, and the OpenAPI `servers` entry                                 |
| `title`, `description`                  | OpenAPI `info.title` and `info.description`                                              |
| `status`                                | Lifecycle badge, and whether PRD serves it, see [Design](#design)                        |
| `scope`                                 | EU-harmonized or country-specific, the grouping on the landing page                      |
| `group`                                 | Authentication, activities or listings, the section on the landing page                  |
| `supersedes_path`, `superseded_by_path` | The "replaces / replaced by" sentences in the OpenAPI description                        |
| `changes`, `diff_url`                   | What this version adds, and the link to the generated diff                               |
| `redirect_slashes`                      | Trailing-slash behavior, see [NLgov REST API Design Rules](#nlgov-rest-api-design-rules) |

Anything that needs the list of domains reads `API_DOMAINS`, never a hard-coded list:
the landing page, the audit middleware skip list, the security headers, and the frozen
OpenAPI snapshot test. Adding a version in one place therefore reaches all of them.
The mounts and the landing page read `served_api_domains()` instead, which leaves out
alpha versions when `API_ALPHA_ENABLED` is off.

---

### Sub-app factory

`app/api/app_factory.py` builds every sub-app the same way. A domain version supplies
only its registry entry and its routers:

```python
app_str_v2, verify_bearer_token = create_domain_app(
    STR_V2,
    [areas_list_v2.router, areas.router, activities_bulk_v2.router, ...],
)
```

The factory adds what all versions share:

- Metadata from the registry, plus `version` and `contact` from the settings (see [NLgov REST API Design Rules](#nlgov-rest-api-design-rules))
- The custom OpenAPI generator (`create_custom_openapi`)
- The shared exception handlers, so every error body is an `Error.Response`
- The common 500 and 503 responses
- The OAuth 2.0 bearer-token security override

FastAPI serves `/openapi.json` itself and injects the mount prefix, so no domain declares
a route for it.

---

### Routers

A router file holds the endpoints of one resource, for one version, in one domain:
`app/api/domains/<domain>/routers/<resource>_v<N>.py`.

What a router is responsible for:

- The path, method, `operation_id`, `summary` and `description`
- The role check, as a dependency: `dependencies=[Depends(RequireRoles(Role.STR, Role.READ))]`
- The query parameters it accepts, composed from the shared filter types
- The **scope**: the part of the data this audience may see, taken from the bearer token, never from a query parameter
- The database session dependency, which is also the transaction boundary

What a router does **not** do: business logic. It calls a shared handler, which calls the
service layer. Example (STR v2 listings):

```python
def _scope(client: ClientDependency) -> ListingScope:
    # Fixed per audience: own listings, flagged only
    return ListingScope(platform_client_id=client.id, status=ListingStatus.flagged)
```

Two conventions keep a router file small:

- Long OpenAPI text and examples live next to it in a `*_docs.py` module, shared by the versions that show the same text
- Repeated logic lives in `app/api/common/*_handlers.py`, shared by every domain that offers the same read

---

### Shared building blocks

Everything under `app/api/common/` is version-independent and domain-independent:

| Module                  | What it offers                                                                |
| ----------------------- | ----------------------------------------------------------------------------- |
| `security.py`           | The `Role` enum and bearer-token verification                                 |
| `auth_dependencies.py`  | `RequireRoles`, and the `Client` identity parsed from the token               |
| `pagination.py`         | `offset` and `limit` parameters, with the per-version default                 |
| `bulk_json.py`          | HTTP status of a bulk result: 201 all OK, 200 partial, 422 all failed         |
| `activity_handlers.py`  | The activity list and count read, shared by CA, STA and AMA                   |
| `listing_handlers.py`   | The listing list and count read, shared by STR, LSA, CA, LMA and STA          |
| `listing_filters.py`    | The listing query-parameter types, so every domain describes them identically |
| `listing_examples.py`   | The listing OpenAPI examples and field text                                   |
| `openapi.py`            | The OpenAPI post-processing hooks, see below                                  |
| `exception_handlers.py` | Maps every exception to the `Error.Response` body                             |
| `routers/`              | The version-independent routers: auth, health, ping                           |

The pattern behind the handlers: **one handler, many scopes**. The handler takes a
`scope` object with no default, the router fills it in. An unscoped read is therefore
never an accident, it has to be written out.

---

### OpenAPI document

FastAPI generates the document; `app/api/common/openapi.py` post-processes it. The hooks
run in order, on every sub-app:

1. `replace_auto_generated_body_schemas` - rename FastAPI's `Body_*` schemas to the dotted names (`Auth.TokenRequest`, `Area.Request`)
2. `remove_fastapi_validation_schemas` - drop `HTTPValidationError` and `ValidationError`, which this API never returns
3. `remove_inapplicable_422_responses` - drop the 422 FastAPI adds to endpoints that never emit it
4. `extract_bulk_item_schemas` - give every bulk item its own component instead of an inline schema, driven by the `BULK_ITEM_SCHEMAS` table
5. `sort_schemas_by_namespace` - sort by dotted title, so the schema list reads per resource
6. `use_bearer_scheme_when_client_credentials_disabled` - show a plain Bearer scheme when the client-secret flow is off

Step 4 needs explaining. A bulk request lists its items as `SkipValidation[ItemRequest]`,
so one invalid item can fail without failing the batch. The side effect is that FastAPI
inlines the item schema. The hook moves it back into `components.schemas`, so the contract
keeps a reusable, concretely-typed item schema.

The generated documents are **frozen** in `backend/tests/api/fixtures/openapi_<domain>_v<N>.snapshot.json`,
one per domain version, and compared on every test run. An unintended contract change
fails the test. An intended one is refreshed with `make api-snapshot-update`, and the
review of that diff is part of the change, see [Implementation (addition)](#implementation-addition).

---

### Adding a version

The recipe, in order:

1. Add the `ApiDomain` entry to `domain_registry.py`, and add it to `API_DOMAINS`; its `group` must be in `API_GROUPS`, a new group needs a heading there
2. Set `superseded_by_path` on the version it replaces, and `supersedes_path` on the new one
3. Add `app/api/domains/<domain>/v<N>.py`, calling `create_domain_app` with the routers
4. Reuse the previous version's routers for everything that does not change; add a new router file only for what does
5. Add it to `DOMAIN_APPS` in `app/main.py`, which mounts it when it is served (alpha: up to PRE only), and to `ALPHA_PREFIXES` in `tests/test_smoketest.py` while it is alpha
6. Add the audit action rules for new endpoints, in `app/security/audit.py`; the audit skip list and the security headers follow `API_DOMAINS`
7. Run `make api-snapshot-update` and `make api-diff-update`, then review both diffs
8. Document it: [Surface](#surface), [Actual versions](#actual-versions), and `CHANGELOG.md`

New functionality goes into the alpha version, never into a beta or a stable one, see
[Design](#design).
