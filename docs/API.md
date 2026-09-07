<h1>API</h1>

This document describes the SDEP API.

<h2>Table of Contents</h2>

- [Principle](#principle)
- [Patterns](#patterns)
- [Domains](#domains)
- [Surface](#surface)
  - [Authentication](#authentication)
  - [Competent Authority (CA)](#competent-authority-ca)
  - [Short-term Rental Platform (STR)](#short-term-rental-platform-str)
  - [Reporting (REP)](#reporting-rep)
  - [Common](#common)
- [Versioning](#versioning)
  - [Contract](#contract)
  - [Status Indicator](#status-indicator)
  - [Actual](#actual)
  - [Diff](#diff)
  - [Operation Ids](#operation-ids)
  - [Add New](#add-new)
  - [Export](#export)
- [Filtering](#filtering)
  - [CA Activity (v2)](#ca-activity-v2)
  - [REP Activity (v1)](#rep-activity-v1)
- [HTTP Status Codes](#http-status-codes)
  - [Success](#success)
  - [Client Errors](#client-errors)
  - [Server Errors](#server-errors)
  - [Error Response Body](#error-response-body)
- [OpenAPI vs Swagger UI](#openapi-vs-swagger-ui)
  - [OpenAPI](#openapi)
  - [Swagger UI](#swagger-ui)
  - [Interchangeable?](#interchangeable)
  - [Example](#example)
  - [Takeaways](#takeaways)
- [API Gateway?](#api-gateway)
  - [Motivation](#motivation)
  - [When](#when)
  - [Conclusion](#conclusion)

## Principle

**Keep the API as simple and concise as possible.**

> REST APIs are one of the most common kinds of web interfaces available today. \
> Therefore, it's very important to design REST APIs properly so that we won't run into problems down the road. \
> Otherwise, we create problems for clients that use our APIs, which isn’t pleasant and detracts people from using our API. \
> If we don’t follow commonly accepted conventions, then we confuse the maintainers of the API and the clients that use them since it’s different from what everyone expects.

---

*<https://stackoverflow.blog/2020/03/02/best-practices-for-rest-api-design/>*

## Patterns

| #          | Decision                                                                                          | Motivation/example                                                                                                     |
| :--------- | :------------------------------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------- |
| **API 01** | Support OpenAPI 3.1.0                                                                             | Swagger 2.0 is legacy - <https://swagger.io/specification/>                                                            |
| **API 02** | All endpoints are self-explanatory/well-documented                                                |                                                                                                                        |
| **API 03** | Use noun instead of verbs                                                                         | Best practice, for example <https://logius-standaarden.github.io/API-Design-Rules/>                                    |
| **API 04** | Use plural nouns for collections and query parameters (with pagination) for filtering collections | Best practice, for example <https://learn.microsoft.com/en-sg/azure/architecture/best-practices/api-design/>           |
| **API 05** | Consistent datamodel                                                                              | Avoid code duplication, e.g. have unified `Activity`, `Area` and error responses                                       |
| **API 06** | Consistent endpoints                                                                              | Collection endpoints, explicit "bulk" qualification where needed: `POST /ca/areas` vs. `POST /str/activities/bulk`     |
| **API 07** | Consistent pagination                                                                             | Have `offset` and `limit` for all endpoints with (potential) many records                                              |
| **API 08** | Syntax validation                                                                                 | Example: `postal code`                                                                                                 |
| **API 09** | Semantical validation                                                                             | Example: `begin timestamp < end timestamp`                                                                             |
| **API 10** | Integrity validation                                                                              | Example: can only submit activities for existing areas                                                                 |
| **API 11** | Bulk POST                                                                                         | All STR activity submissions use `POST /str/activities/bulk` (up to 1000 items/batch)                                  |
| **API 12** | Logical ordering => readability                                                                   | For POST, request and response follow the same ordering, extra data in response (e.g. `createdAt`) is moved to the end |
| **API 13** | Essentiality                                                                                      | Example: in `/str/activities/bulk`, only `areaId`, but no `competentAuthorityId`                                       |
| **API 14** | Essentiality/security                                                                             | Example: in POST activities, no need to include `platformId`                                                           |
| **API 15** | Consistent HTTP response codes                                                                    | See [HTTP Status Codes](#http-status-codes) below                                                                      |
| **API 16** | STR and CA: manage area change                                                                    | Areas may change over time, SDEP only administrates the changes and exposes the latest "truth"                         |
| **API 17** | Unified response format                                                                           | Example: `ActivityResponse` (for STR and CA, both contain `competentAuthorityName`')                                   |

## Domains

API-endpoints are exposed in the following domains:

- Authentication
- Competent authority (CA)
- Short-term rental platform (STR)
- Reporting & statistics (REP)
- Common (ping & health)

## Surface

---

### Authentication

- `POST /api/auth/v1/token` - OAuth 2.0 token endpoint

---

### Competent Authority (CA)

**Areas**

**v1**

- `POST /api/ca/v1/areas` - Submit a single area (multipart/form-data: file + optional areaId, areaName)
- `GET /api/ca/v1/areas` - List own areas (pagination: offset, limit)
- `GET /api/ca/v1/areas/count` - Count own areas
- `GET /api/ca/v1/areas/{areaId}` - Download shapefile for own area
- `DELETE /api/ca/v1/areas/{areaId}` - Delete (deactivate) an own area

**v2 - unchanged**

The area endpoints are mounted unchanged into v2, so every `/api/ca/v1/areas...` path above is also served at `/api/ca/v2/areas...`, with the same request, response, and authorization. Only the activity endpoints differ between the two versions.

---

**Activities**

**v1**

- `GET /api/ca/v1/activities` - Query rental activities (pagination: offset, limit)
- `GET /api/ca/v1/activities/count` - Count activities

**v2 - adds optional query filters**

- `GET /api/ca/v2/activities` - Query rental activities with optional filters (pagination: offset, limit; filters: filterCreatedAtFrom, filterCreatedAtTo, filterPlatformId, filterAreaId; filters use AND semantics and are scoped to the authenticated CA; createdAt filters must be UTC)
- `GET /api/ca/v2/activities/count` - Count activities with optional filters (same filter set)

---

### Short-term Rental Platform (STR)

**Areas**

**v1**

- `GET /api/str/v1/areas` - List regulated areas (pagination: offset, limit)
- `GET /api/str/v1/areas/count` - Count areas
- `GET /api/str/v1/areas/{areaId}` - Download shapefile for area

---

**Activities**

**v1**

- `POST /api/str/v1/activities/bulk` - Submit up to 1000 activities in bulk (JSON body)

---

### Reporting (REP)

**Activities**

**v1**

Read-only endpoints for the national statistics office (no write endpoints registered; POST/PUT/PATCH/DELETE return 405):

- `GET /api/rep/v1/activities` - Query rental activities across all competent authorities and platforms (pagination: offset, limit - limit defaults to 1000, the maximum; filters: filterCreatedAtFrom, filterCreatedAtTo, filterPlatformId, filterAreaId, filterCompetentAuthorityId - AND semantics; createdAt filters must be UTC; invalid functional IDs or non-UTC datetimes → 400)
- `GET /api/rep/v1/activities/count` - Count activities with optional filters (same filter set)

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

---

## Versioning

---

### Contract

The API version (contract) is embedded in the URL path (`/api/{domain}/v1/...`).

A new API version (e.g. from v1 to v2) is introduced:

- **Mandatory**: when an unavoidable **breaking change** is made to the contract.
- E.g. removing or renaming a field, changing a field's type, or altering its semantics.
- **Optional**: when new functionality is introduced that is **not necessarily breaking**, is already exposed to consumers, but is still under development and subject to change.
  - E.g. additional query filters in `ca/v2`

When a new API version is released, the previous version (N-1) remains available for a deprecation period to give clients time to migrate.

- Only the current (N) and previous (N-1) versions are supported simultaneously.

---

### Status Indicator

Each API version has a status:

- **Stable** - supported for production integrations
  - Application [backward compatibility](./ARCHITECTURE_TECH.md#application-versioning) is guaranteed within the same API version.
- **Alpha**:
  - Early-stage and unstable.
  - Available for early integration and feedback.
  - The contract is expected to change before it is promoted to beta or stable.
- **Beta**:
  - Rather stable and feature-complete.
  - Available for early integration and feedback.
  - The contract may still change before it is promoted to stable.

A beta API can be available in production. Clients may integrate with it, but the contract may change.

The endpoints each version exposes are listed in [Surface](#surface), and the per-operation difference between consecutive versions is in [API Version Diff](API_DIFF.md).

---

### Actual

| Domain | Version | Status | Notes                                               |
| ------ | ------- | ------ | --------------------------------------------------- |
| auth   | v1      | stable | OAuth 2.0 token endpoint (client credentials)       |
| ca     | v1      | stable | Areas + activities (no filters)                     |
| ca     | v2      | beta   | Activities with optional query filters (new)        |
| str    | v1      | stable | Areas (read-only) + bulk activity submission        |
| rep    | v1      | beta   | Read-only reporting API for reporting offices (new) |

---

### Diff

The differences between consecutive API versions are generated from the committed OpenAPI snapshots and published in [API Version Diff](API_DIFF.md). The document is regenerated with `make api-diff-update` from `backend/` and is gated by the backend test suite, so it cannot drift from the contract.

In short: CA v2 is CA v1 plus four optional activity filters. No path, schema, response, or authorization changes. See [CA Activity (v2)](#ca-activity-v2) for the parameters themselves.

Each version also carries its own cross-version note in the OpenAPI `info.description`, so it is visible at the top of that version's Swagger UI without leaving the API.

Deprecation markers (`deprecated: true` on the superseded operations, and the `Deprecation` and `Sunset` response headers) are deliberately not set yet: v1 is stable and v2 is beta, so v1 is not being retired. They become correct once v2 is promoted to stable and a retirement date is set.

---

### Operation Ids

Every operation carries an explicit `operationId`, which client code generators turn into a method name.

- Operations that a new version redefines carry a `VN` suffix from v2 onward, for example `getActivityByCompetentAuthorityV2` and `countActivitiesV2`. This keeps the ids unique across the versions that co-exist
- Operations that a new version mounts unchanged keep a single id across versions. The five area operations (`postArea`, `getOwnAreas`, `countOwnAreas`, `getOwnArea`, `deleteOwnArea`) are shared by CA v1 and CA v2 and are therefore not suffixed

A consequence is that the generated version diff reports an `operationId` change for the redefined operations. That is intended, not drift.

---

### Add New

Each domain is exposed as one or more independently-versioned FastAPI sub-applications,
mounted side by side (e.g. `/api/ca/v1`, `/api/ca/v2`). A new version is additive:
existing versions stay byte-compatible.

Shared vs. version-specific code (CA domain as example):

- Shared (one source of truth, used by every version):
  - `app_factory.py` - `create_domain_app(domain, routers)` builds the sub-app (title,
    common 500/503 responses, OpenAPI, exception handlers, bearer-token override,
    `openapi.json` route)
  - `domain_registry.py` - per-version metadata (label, title, description, status) and
    the cross-version links that render the "Changes from ..." / "Superseded by ..." note
    into the OpenAPI description
  - `common/activity_handlers.py` - the endpoint business logic (list/count)
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
difference between consecutive versions is generated into [API Version Diff](API_DIFF.md).
Both are gated by the backend test suite: change an endpoint and the suite fails until
`make api-snapshot-update` and `make api-diff-update` have been run and the diff reviewed.

---

### Export

API PDF export for specific API versions:

- [API auth_v1 pdf](./sdep_openapi_auth_v1.pdf)
- [API ca_v1 pdf](./sdep_openapi_ca_v1.pdf)
- [API str_v1 pdf](./sdep_openapi_str_v1.pdf)

> Disclaimer: These PDFs were generated as part of the v1 freeze on 28 April 2026. While the /v1 API is frozen, implementation details may still differ in certain cases (see the [changelog](../CHANGELOG.md) for updates).

---

## Filtering

---

### CA Activity (v2)

`GET /api/ca/v2/activities` and `GET /api/ca/v2/activities/count` accept optional query parameters to narrow results within the authenticated CA's scope:

| Parameter             | Type         | Description                                          |
| --------------------- | ------------ | ---------------------------------------------------- |
| `filterCreatedAtFrom` | datetime     | Inclusive lower bound on `createdAt` (ISO 8601, UTC) |
| `filterCreatedAtTo`   | datetime     | Inclusive upper bound on `createdAt` (ISO 8601, UTC) |
| `filterPlatformId`    | FunctionalId | Exact-match filter on `platformId`                   |
| `filterAreaId`        | FunctionalId | Exact-match filter on `areaId`                       |

All provided filters are combined with AND semantics. Omitting a filter means no constraint on that dimension. The `filterCreatedAtFrom` and `filterCreatedAtTo` values must be expressed in UTC (offset `Z` or `+00:00`); naive datetimes or other offsets return HTTP 400, following the API convention for invalid GET query parameters. An invalid `FunctionalId` format also returns HTTP 400.

If OR semantics are required, clients should implement them client-side by calling this endpoint multiple times and combining the results.

---

### REP Activity (v1)

`GET /api/rep/v1/activities` and `GET /api/rep/v1/activities/count` are read-only endpoints for reporting offices, such as a statistics office (in SDEP-NL, this is the Centraal Bureau voor de Statistiek). They return all current activities across all competent authorities and platforms, and accept the same optional query parameters as CA v2 plus one extra:

| Parameter                    | Type         | Description                                          |
| ---------------------------- | ------------ | ---------------------------------------------------- |
| `filterCreatedAtFrom`        | datetime     | Inclusive lower bound on `createdAt` (ISO 8601, UTC) |
| `filterCreatedAtTo`          | datetime     | Inclusive upper bound on `createdAt` (ISO 8601, UTC) |
| `filterPlatformId`           | FunctionalId | Exact-match filter on `platformId`                   |
| `filterAreaId`               | FunctionalId | Exact-match filter on `areaId`                       |
| `filterCompetentAuthorityId` | FunctionalId | Exact-match filter on `competentAuthorityId`         |

All provided filters are combined with AND semantics. The `filterCreatedAtFrom` and `filterCreatedAtTo` values must be expressed in UTC (offset `Z` or `+00:00`); naive datetimes or other offsets return HTTP 400, following the API convention for invalid GET query parameters. An invalid `FunctionalId` format also returns HTTP 400. The REP API requires the `sdep_rep` and `sdep_read` roles and registers no write endpoints: POST, PUT, PATCH, and DELETE return HTTP 405.

`GET /api/rep/v1/activities` returns at most 1000 records per request: the `limit` parameter defaults to 1000 (also the maximum). Use `offset` together with `GET /api/rep/v1/activities/count` to page through larger result sets.

## HTTP Status Codes

---

### Success

| HTTP Status | Meaning    | When                                                                                                |
| ----------- | ---------- | --------------------------------------------------------------------------------------------------- |
| 200         | OK         | GET request completed successfully; bulk POST with partial success (created multiple new resources) |
| 201         | Created    | POST request created a single new resource                                                          |
| 204         | No Content | DELETE request completed successfully (e.g. deactivate area)                                        |

---

### Client Errors

| HTTP Status | Meaning               | When                                                                                                                                                                              |
| ----------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 400         | Bad Request           | Invalid query parameters on a GET request (e.g. `offset=-1` or `limit=abc`), or missing client credentials                                                                        |
| 401         | Unauthorized          | Missing, invalid, or expired authentication token; missing required token claims (`client_id`, `client_name`)                                                                     |
| 403         | Forbidden             | Authenticated but missing a required role (`sdep_ca`, `sdep_str`, `sdep_read`, `sdep_write`)                                                                                      |
| 404         | Not Found             | Requested resource does not exist, is unavailable, or has been deleted                                                                                                            |
| 409         | Conflict              | Duplicate resource (unique constraint violation)                                                                                                                                  |
| 413         | Payload Too Large     | Upload exceeds the per-endpoint size limit (e.g. `POST /api/ca/v1/areas` rejects requests whose `Content-Length` exceeds the 1 MiB file-size cap plus a small multipart envelope) |
| 422         | Unprocessable Content | Invalid request body on a POST request (e.g. missing required field) or business rule violation (e.g. start time > end time)                                                      |

---

### Server Errors

| HTTP Status | Meaning               | When                                                                     |
| ----------- | --------------------- | ------------------------------------------------------------------------ |
| 500         | Internal Server Error | Unexpected condition that prevented fulfilling the request (catch-all)   |
| 503         | Service Unavailable   | Database or authorization server (e.g. Keycloak) temporarily unavailable |

For the mapping between application exceptions and HTTP status codes, see [Exceptions](ARCHITECTURE_TECH.md#exceptions) in the Technical Architecture document.

---

### Error Response Body

Application errors (validation, authorization, business rules, and similar) use the standardized `Error.Response` schema (`ErrorResponse` in code, see `backend/app/schemas/error.py`): a JSON object whose `detail` is a list of error objects, each with `msg`, `type`, and an optional `loc`.

A few framework-level responses are produced by FastAPI's router before a request reaches application code, and these use FastAPI's default body shape instead, where `detail` is a plain string rather than the standardized list:

- 405 Method Not Allowed (e.g. a write method on the read-only REP API)
- Routing-level 404 Not Found (a path that matches no registered route)

This is intentional and behaves identically across the CA, STR, and REP APIs.

---

## OpenAPI vs Swagger UI

---

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
GET /api/rep/v1/openapi.json
```

It is the **authoritative, machine-readable contract** of the API.

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
GET /api/rep/v1/docs
```

A landing page at `GET /api/docs` links to all domain docs.

Swagger UI's audience is humans: developers exploring the API, integrators drafting their first request, reviewers sanity-checking a change.

To keep that audience oriented, Swagger UI **summarizes where the raw spec would overwhelm** - e.g. it may label a field as `array<object>` even when the spec contains a named `$ref` to a typed component. The typed detail is still reachable (one click deeper), but the top-level label is deliberately compact.

---

### Interchangeable?

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

---

## API Gateway?

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
