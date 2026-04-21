<h1>API</h1>

This document describes principles and patterns for the SDEP API.

Table of contents

- [Principle](#principle)
- [Patterns](#patterns)
- [HTTP status codes](#http-status-codes)
  - [Success](#success)
  - [Client errors](#client-errors)
  - [Server errors](#server-errors)
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

*https://stackoverflow.blog/2020/03/02/best-practices-for-rest-api-design/*

## Patterns

| #               | Decision                                           | Motivation/example                                                                                                     |
| :-------------- | :------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| **API&nbsp;01** | Support OpenAPI 3.1.0                              | Swagger 2.0 is legacy - https://swagger.io/specification/                                                              |
| **API&nbsp;02** | All endpoints are self-explanatory/well-documented |                                                                                                                        |
| **API&nbsp;03** | Use nouns instead of verbs                         | Best practice - https://logius-standaarden.github.io/API-Design-Rules/                                                 |
| **API&nbsp;04** | Use plurals for resources that affect collections  | Best practice - https://logius-standaarden.github.io/API-Design-Rules/                                                 |
| **API&nbsp;05** | Consistent datamodel                               | Avoid code duplication, e.g. have unified `Activity`, `Area` and error responses                                       |
| **API&nbsp;06** | Consistent endpoints                               | Have POST/GET "mirrors": `POST /ca/areas`, `GET /ca/activities`, `POST /str/activities/bulk`, `GET /str/areas`         |
| **API&nbsp;07** | Consistent pagination                              | Have `offset` and `limit` for all endpoints with (potential) many records                                              |
| **API&nbsp;08** | Syntax validation                                  | Example: `postal code`                                                                                                 |
| **API&nbsp;09** | Semantical validation                              | Example: `begin timestamp < end timestamp`                                                                             |
| **API&nbsp;10** | Integrity validation                               | Example: can only submit activities for existing areas                                                                 |
| **API&nbsp;11** | Bulk POST                                          | All STR activity submissions use `/str/activities/bulk` (up to 1000 items/batch)                                       |
| **API&nbsp;12** | Logical ordering => readability                    | For POST, request and response follow the same ordering, extra data in response (e.g. `createdAt`) is moved to the end |
| **API&nbsp;13** | Essentiality                                       | Example: in POST activities, only `areaId` and `competentAuthorityId`, but no `competentAuthorityName`                 |
| **API&nbsp;14** | Essentiality/security                              | Example: in POST activities, no need to include `platformId`                                                           |
| **API&nbsp;15** | Consistent HTTP response codes                     | See [HTTP status codes](#http-status-codes) below                                                                      |
| **API&nbsp;16** | STR and CA: manage area change                     | Areas may change over time, SDEP only administrates the changes and exposes the latest "truth"                         |
| **API&nbsp;17** | Unified response format                            | Example: `ActivityResponse` (for STR and CA, for both contains `competentAuthorityId` and `competentAuthorityName`')   |

---

## HTTP status codes

### Success

| HTTP Status | Meaning    | When                                                                                                |
| ----------- | ---------- | --------------------------------------------------------------------------------------------------- |
| 200         | OK         | GET request completed successfully; bulk POST with partial success (created multiple new resources) |
| 201         | Created    | POST request created a single new resource                                                          |
| 204         | No Content | DELETE request completed successfully (e.g. deactivate area)                                        |

### Client errors

| HTTP Status | Meaning               | When                                                                                                                          |
| ----------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 400         | Bad Request           | Invalid query parameters on a GET request (e.g. `offset=-1` or `limit=abc`), or missing client credentials                    |
| 401         | Unauthorized          | Missing, invalid, or expired authentication token; missing required token claims (`client_id`, `client_name`)                 |
| 403         | Forbidden             | Authenticated but missing a required role (`sdep_ca`, `sdep_str`, `sdep_read`, `sdep_write`)                                  |
| 404         | Not Found             | Requested resource does not exist, is unavailable, or has been deleted                                                        |
| 409         | Conflict              | Duplicate resource (unique constraint violation)                                                                              |
| 422         | Unprocessable Content | Invalid request body on a POST request (e.g. missing required field), or business rule violation (e.g. start time > end time) |

### Server errors

| HTTP Status | Meaning               | When                                                                   |
| ----------- | --------------------- | ---------------------------------------------------------------------- |
| 500         | Internal Server Error | Unexpected condition that prevented fulfilling the request (catch-all) |
| 503         | Service Unavailable   | Database or authorization server (Keycloak) temporarily unavailable    |

For the mapping between application exceptions and HTTP status codes, see [Exception Handling](ARCHITECTURE_TECH.md#exception-handling) in the Architecture document.

---

## OpenAPI vs Swagger UI

### OpenAPI

The **[OpenAPI Specification](https://www.openapis.org/)** (formerly *Swagger Specification*) is a language-agnostic standard (currently 3.1.0) for describing HTTP APIs.

- A single document enumerates every endpoint, its request parameters and body, its response shapes per HTTP status code, its authentication scheme, and the data types (`components.schemas`) those endpoints consume and produce
- With constraints like lengths, patterns, enums, required fields, and examples

SDEP exposes this document at:

```
GET /api/v0/openapi.json
```

It is the **authoritative, machine-readable contract** of the API.

- FastAPI generates it automatically from the Pydantic schemas and route definitions in the code, so it is always in sync with the running backend
- It is what client code generators (e.g. [openapi-generator](https://openapi-generator.tech/), [openapi-typescript](https://github.com/openapi-ts/openapi-typescript)), contract-test tools, mock servers, schema registries, and spec-diff tools consume

Key properties:

- **Versioned, machine-readable** — diffable in git, consumable by tooling.
- **Single source of truth** — endpoints, schemas, and examples live in one document.
- **Reusable components** — named schemas (`#/components/schemas/...`) are referenced via `$ref` so the same type can appear in many places without duplication.

### Swagger UI

**[Swagger UI](https://swagger.io/tools/swagger-ui/)** is an interactive, browser-based **renderer** of an OpenAPI document.

- It is *not* a separate specification or a separate source of truth
- It reads the same `openapi.json` and presents it as a navigable page with collapsible endpoints, schema trees, and a built-in "Try it out" form that submits live requests against the running backend

SDEP serves it at:

```
GET /api/v0/docs
```

Swagger UI's audience is humans: developers exploring the API, integrators drafting their first request, reviewers sanity-checking a change.

To keep that audience oriented, Swagger UI **summarizes where the raw spec would overwhelm** — e.g. it may label a field as `array<object>` even when the spec contains a named `$ref` to a typed component. The typed detail is still reachable (one click deeper), but the top-level label is deliberately compact.

### Interchangeable?

The two are not interchangeable:

- When a schema is non-trivial (arrays of typed objects, composed `$ref`s, polymorphism), Swagger UI summarizes while the raw JSON retains the full detail
- Always treat `openapi.json` as the source of truth

### Example

`POST /str/activities/bulk`

The bulk endpoint's request body is `ActivityBulkRequest`, whose `activities` field is an array of `ActivityRequest`. The contract expresses this precisely; Swagger UI renders it in a more compact way.

**1. Swagger UI (Schema tab)**

Swagger UI shows the request body as `ActivityBulkRequest (object)`. The `activities*` property is labeled:

```
activities*   array<object>   [1, 1000] items
```

— i.e. Swagger UI's item-type label is the generic word `object`, not `ActivityRequest`. The typed structure is still there, just one level deeper: expanding `Items` reveals a nested `object` block with every `ActivityRequest` property (`activityId`, `activityName`, `areaId`, `address`, `registrationNumber`, `numberOfGuests`, `countryOfGuests`, `temporal`, …) including their constraints, examples, and descriptions. So Swagger UI does render the full schema; it just does not surface the referenced **type name** at the array level.

**2. openapi.json — request body reference**

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

**3. openapi.json — `ActivityBulkRequest` definition**

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

**4. openapi.json — `ActivityRequest` definition**

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

### Takeaways

- **Typing is explicit in `openapi.json`**, via chained `$ref`s: the endpoint → `ActivityBulkRequest` → `ActivityRequest`. Client code generators, contract-test tools, and spec-diff tools will pick this up and produce typed models.
- **Swagger UI's `array<object>` label is cosmetic**, not a loss of schema detail. The underlying typed item schema is still available one click deeper under *Items*.
- **Consume `openapi.json` for machine workflows** (code generation, conformance tests, contract diffs). **Use Swagger UI for exploratory human reading** and manual request submission.
- **When a spec question arises, check `openapi.json` first.** If a type appears to be "just an object" in Swagger UI, it almost always has a named component behind it — follow the `$ref`.

---

## API Gateway?

For production use in your own country, the utilization of a separate API gateway can be considered (on top of the SDEP API).

Within **SDEP NL**, a dedicated API gateway is currently **not** used. This is a deliberate choice based on how the platform is designed and operated. Only when specific edge-control requirements arise that cannot be handled by the existing ingress/reverse proxy setup, an additional gateway could be introduced.

### Motivation

In context of SDEP NL:

- **SDEP NL already provides clear API boundaries** \
  The SDEP API itself acts as a functional gateway for data exchange, with well-defined domains (`str` vs `ca`), OAuth2 client credential flows, and strict role separation.

- **Workload is primarily transactional, not cache-driven** \
  Typical interactions (e.g. `POST /str/activities/bulk`, area upload/download) are write-heavy or data-exchange oriented, limiting the value of traditional API gateway features like response caching.

- **Existing edge setup is sufficient and controlled** \
  A hardened edge (ingress/reverse proxy + TLS termination) already provides the necessary entrypoint security and routing without introducing additional layers.

- **Operational simplicity is a key design principle** \
  Avoiding an extra gateway reduces:
  - latency in the request path
  - duplication of security and routing policies
  - risk of configuration drift
  - an additional operational and failure domain

- **Authorization is intentionally handled at the right layers** \
  Identity and access control are enforced via the identity provider and the application itself, aligning with SDEP’s architecture rather than shifting logic to an external gateway.

### When

Introducing a gateway could become relevant when concrete needs arise, such as:

1. Platform-scale **rate limiting or quota management per client**
2. **Centralized security/policy enforcement** across multiple backend services (JWT claim rules, IP allowlists, mTLS, schema checks)
3. Need for **API product capabilities** (developer portal, client onboarding, usage analytics)
4. **Multi-service backend exposure** with a single stable external contract

### Conclusion

SDEP NL prioritizes a **simple, robust edge architecture**. A dedicated API gateway should only be introduced when clear non-functional requirements outweigh the added complexity.
