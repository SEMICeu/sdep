<h1>Integration test scripts</h1>

The [../tests](../tests) directory contains standalone Python scripts for integration testing the SDEP (Single Digital Entry Point) API endpoints.

These tests verify API functionality, authentication, authorization, and security compliance.

- [Running tests](#running-tests)
- [Configuration](#configuration)
  - [Credentials](#credentials)
  - [Bearer tokens](#bearer-tokens)
  - [Exit codes](#exit-codes)
  - [Test data lifecycle](#test-data-lifecycle)
  - [Test suites](#test-suites)
  - [API versions](#api-versions)
- [Coverage](#coverage)
  - [`test-smoke`](#test-smoke)
  - [`test-full`](#test-full)
  - [`test-full-keep`](#test-full-keep)
  - [`test-full-verbose`](#test-full-verbose)
  - [`test-ca`](#test-ca)
  - [`test-str`](#test-str)
  - [`test-sta`](#test-sta)
  - [`test-lsa`](#test-lsa)
  - [`test-lma`](#test-lma)
  - [`test-ama`](#test-ama)
  - [`test-security`](#test-security)
  - [`test-migrations`](#test-migrations)
  - [`test-malware`](#test-malware)
- [Helper scripts](#helper-scripts)
  - [`test_auth_client_bootstrap.py`](#test_auth_client_bootstrappy)
  - [`test_health_ping.py`](#test_health_pingpy)
  - [`lib/create_fixture_areas.py`](#libcreate_fixture_areaspy)

## Running tests

See [../Makefile](../Makefile).

## Configuration

### Credentials

Default test clients are configured in Keycloak. The current integration test
scripts authenticate with the `client_id`/`client_secret` token path, so the
backend must run with `CLIENT_SECRET_AUTH_ENABLED=true` for these tests.
Client-secret is one of the two supported auth methods and is disabled in PRD.
The Makefile retrieves secrets dynamically via `get_client_secret`:

**Competent Authority (CA)**

- **Client ID:** `sdep-test-ca.01`
- **Roles:** `sdep_ca`, `sdep_write`, `sdep_read`
- **Can access:** CA endpoints

**STR Platform**

- **Client ID:** `sdep-test-str.01`
- **Roles:** `sdep_str`, `sdep_write`, `sdep_read`
- **Can access:** STR platform endpoints

**Statistics Authority (STA)**

- **Client ID:** `sdep-test-sta.01`
- **Roles:** `sdep_sta`, `sdep_read` (read-only, no write role)
- **Can access:** STA endpoints

**Listing Screening Authority (LSA)**

- **Client ID:** `sdep-test-lsa.01`
- **Roles:** `sdep_lsa`, `sdep_write`, `sdep_read`
- **Can access:** LSA endpoints

**Listing Monitoring Authority (LMA)**

- **Client ID:** `sdep-test-lma.01`
- **Roles:** `sdep_lma`, `sdep_read` (read-only, no write role)
- **Can access:** LMA endpoints

**Activity Monitoring Authority (AMA)**

- **Client ID:** `sdep-test-ama.01`
- **Roles:** `sdep_ama`, `sdep_read` (read-only, no write role)
- **Can access:** AMA endpoints

---

### Bearer tokens

- Tokens are saved to `./tmp/.bearer_token` by `test_auth_client_bootstrap.py`
- Other scripts automatically load tokens from this file
- Token location is configurable via `TOKEN_FILE` environment variable

---

### Exit codes

All test scripts follow standard Unix exit codes:

- `0` - All tests passed
- `1` - Test failed or error occurred

---

### Test data lifecycle

Everything a test run creates is named `sdep-test-*` and owned by the `sdep-test-*` machine clients, and [`postgres/clean-testrun.sql`](../postgres/clean-testrun.sql) removes exactly that. One shared SQL file serves both the integration and the performance runner, so the cleanup never distinguishes between the two kinds of data.

- An ordinary integration run pre-cleans, runs, then post-cleans, which is what makes it idempotent
- An ordinary performance run only post-cleans; there is no pre-clean, so leftover rows do inflate the tables a run measures against
- `KEEP_TEST_DATA=true` is the single flag for both runners (`test-full-keep`, `test-perf-keep`); it skips that run's **own** cleanup, and nothing more
- Kept data of either kind is therefore removed by the next ordinary run of *either* kind - the two keep modes do not collide, they clear each other
- No keep mode can outlive that next run. The cleanup deletes the `sdep-test-ca.01` competent authority and the `sdep-test-str.01` platform themselves, and the foreign keys take everything they own with them, whatever the rows are named
- The isolation check is unaffected: its baseline is captured *after* the pre-clean, so leftover rows cannot cause a false failure. The displayed BEFORE count is that baseline; the count before the pre-clean is shown next to it when it differs
- `make postgres-clean-testrun` is the manual recovery path, for a run that could not clean up (aborted, or the database was unreachable) or when you are done with kept data
- Loaded and non-`sdep-test-*` data is never touched. `make postgres-drop` is the only thing that clears everything

Note that two of the four deletes match on the functional id (`area_id` / `activity_id LIKE 'sdep-test-%'`) rather than on the owning client. An area or activity literally named `sdep-test-...` but created by a preserved client would therefore be removed. The predefined test data does not use that naming.

`clean-testrun.sql` never removes `audit_log` rows. An empty entity count alongside a populated audit log is the normal result of a clean-up, not a defect.

---

### Test suites

[`tests/suites.txt`](../tests/suites.txt) is the single list of integration test runs, for the local runner and the deployment runner alike.

- One line per run: suite, client, test, API version, and an `x` per environment (DEV = local stack, TST, ACC, PRE, PRD)
- A suite runs as one group, in file order; the runner logs in as the suite's client first (`-` = no login)
- `scripts/suites.sh <env> [<suite>]` prints the runs of one environment; `make test-<suite>` runs one suite locally (`scripts/run-suite.sh`)
- A new test means new lines in this file, and it runs everywhere its `x` says
- The environment columns can be adjusted to your own needs. PRD only runs the `smoke` suite: production has no test clients and takes no test data.
- `make test-suites` (also a CI/CD check) fails when a test script is in no suite and not deliberately excluded, or when the file is malformed

`test_auth_client_jwt` is not in a suite: it needs a client and key per environment, so the runners call it separately (see [`test-security`](#test-security)).

---

### API versions

A versioned test runs once per API version that exists, so older versions stay tested (backwards compatibility).

- [`tests/suites.txt`](../tests/suites.txt) has one line per test and version (see [Test suites](#test-suites))
- The runner passes each version to the test as `API_VERSION`
- An environment column can leave out a version, for example an alpha version where it is not served
- `scripts/api-versions.sh <test>` prints the versions of one test, for consuming repositories that predate `scripts/suites.sh`
- A new API version means new lines in that file, for both runners

| Test                                                           | Versions | Note                                                        |
| -------------------------------------------------------------- | -------- | ----------------------------------------------------------- |
| `test_auth_headers`                                            | v1, v2   | Headers of the CA OpenAPI document and Swagger UI           |
| `test_ca_areas`                                                | v1, v2   |                                                             |
| `test_ca_activities`                                           | v1, v2   | v1 and v2 declare the query filters                         |
| `test_ca_listings`                                             | v2       | Listings exist only in v2                                   |
| `test_str_areas`                                               | v1, v2   | v2 defaults `limit` to 1000                                 |
| `test_str_activities`                                          | v1, v2   | v2 requires UTC timestamps                                  |
| `test_str_listings`                                            | v2       | Listings exist only in v2                                   |
| `test_sta_activities`                                          | v1, v2   |                                                             |
| `test_sta_listings`, `test_lsa_listings`, `test_lma_listings`  | v2       | Listings exist only in v2                                   |
| `test_ama_activities`                                          | v1       | One version today                                           |
| `test_reference_data`                                          | v1, v2   | Only the domain versions that serve reference data          |
| `test_auth_client_secret`, `test_auth_client_jwt`              | v1       | Not listed: the auth API has one version                    |
| `test_smoketest`, `test_health_ping`, `test_auth_unauthorized` | -        | Not versioned: they cover the versions they need themselves |

Version-specific checks in a test compare against `v1` (`api_version != "v1"`). A newer version therefore gets the v2 checks, which is correct as long as each version only adds endpoints to the one before.

## Coverage

### `test-smoke`

Smoke test for audit-excluded endpoints (SKIP_PATHS).

**Script:** `test_smoketest.py`

**What it tests:**

- All audit-excluded, unauthenticated endpoints return HTTP 200
- With `API_ALPHA_ENABLED=false` (PRD), the alpha endpoints return HTTP 404 instead, see the API versioning [design](./API_TECH.md#design)
- Safe for production: read-only, no authentication, no test data

**Endpoints tested:**

- `/` - Root endpoint
- `/api/docs` - Landing page
- `/api/health` - Health check
- `/api/auth/v1/openapi.json` - Auth OpenAPI spec
- `/api/auth/v1/docs` - Auth Swagger UI
- `/api/ca/v{1,2,3}/openapi.json` and `/docs` - CA OpenAPI spec and Swagger UI per version
- `/api/str/v{1,2,3}/openapi.json` and `/docs` - STR OpenAPI spec and Swagger UI per version
- `/api/{lsa,lma,ama,sta}/v1/openapi.json` and `/docs` - the v1 spec and Swagger UI of the other domains

**Required environment variables:**

- `BACKEND_BASE_URL` - API base URL

**Optional environment variables:**

- `API_ALPHA_ENABLED` - `false` for PRD (default `true`)

---

### `test-full`

Test fullstack (quiet). Runs `test-full-verbose` and filters output to the results summary.

---

### `test-full-keep`

Test fullstack (quiet, keep test data). Same as `test-full` but skips cleanup of `sdep-test-*` rows after the run.

---

### `test-full-verbose`

Test fullstack (verbose). Runs all suites below via `scripts/run-tests.sh` with full output and PRE/POST row count isolation checks. A test that cannot run (no sample data, missing credentials) counts as skipped: it is shown in the totals with ⚠️, but does not fail the run.

---

### `test-ca`

Test CA (Competent Authority) endpoints.

**Scripts:** `test_ca_areas.py`, `test_ca_listings.py`, `test_ca_activities.py`

---

**`test_ca_areas.py`**

**Tests:**

- **Test 1:** POST single area with shapefile upload and areaId
- **Test 2:** POST with custom areaId field
- **Test 3:** POST without areaId (auto-generated UUID)
- **Test 4:** GET own areas (`GET /ca/areas`)
- **Test 5:** GET own areas count (`GET /ca/areas/count`)
- **Test 6:** GET own areas does not contain endedAt
- **Test 7:** Versioning - submit same areaId twice
- **Test 8:** DELETE area (deactivate) → 204
- **Test 9:** DELETE nonexistent area → 404
- **Test 10:** GET own area by ID → 200 OK
- **Test 11:** GET nonexistent own area by ID → 404
- **Test 12:** Cross-CA isolation - two CAs POSTing the same `areaId` each keep their own area (regression guard for cross-CA area isolation). Requires `CA2_CLIENT_ID`/`CA2_CLIENT_SECRET`; skipped otherwise.

**Endpoints:**

- `POST /api/ca/{API_VERSION}/areas`
- `GET /api/ca/{API_VERSION}/areas`
- `GET /api/ca/{API_VERSION}/areas/count`
- `GET /api/ca/{API_VERSION}/areas/{areaId}`
- `DELETE /api/ca/{API_VERSION}/areas/{areaId}`

**Content-Type:** `multipart/form-data` (POST)

**Authentication:** Requires CA client credentials (token loaded from `./tmp/.bearer_token`)

**Payload:** Form fields: `file` (shapefile upload), `areaId` (optional), `areaName` (optional). Uses `test-data/shapefiles/Amsterdam.zip`.

**HTTP Status Codes:**

- `201 Created` - Area successfully created
- `204 No Content` - Area successfully deleted (deactivated)
- `401 Unauthorized` - No/invalid authentication
- `404 Not Found` - Area not found (DELETE)
- `422 Unprocessable Content` - Validation error

**Response format:** `{ areaId, areaName?, filename, competentAuthorityId, competentAuthorityName, createdAt }` (POST/GET); no body (DELETE)

---

**`test_ca_listings.py`**

**Tests:** the same tests as `test_sta_listings.py`, against `GET /ca/v2/listings` and `GET /ca/v2/listings/count` (fixed scope: acknowledged listings in the authority's own areas; role isolation with an STR token)

**Authentication:** Requires CA client credentials (token loaded from `./tmp/.bearer_token`)

---

**`test_ca_activities.py`**

`make test-ca` runs this script once per version (v1, v2, see [API versions](#api-versions)). Tests 6-10 discover a sample activity (`?limit=1`) and derive the filter values from it, so no IDs are hard-coded; with no data they pass with a note.

**Tests:**

- **Test 1:** Count activities (`GET /ca/{API_VERSION}/activities/count`)
- **Test 2:** Get all activities
- **Test 3:** Pagination (offset=0, limit=1)
- **Test 4:** Verify response structure (activityId, activityName, status, platformId, platformName, url, registrationNumber, address, temporal, areaId)
- **Test 5:** GET by `url` query parameter (not declared in any version; endpoint must still respond)
- **Test 6:** Filter by `areaId`
- **Test 7:** Filter by `platformId`
- **Test 8:** Filter by `createdAtFrom` / `createdAtTo` (both equal to the sample's `createdAt`)
- **Test 9:** Non-matching `areaId` filter
- **Test 10:** `/count` with filter matches the length of the filtered list (one page, max 1000)
- **Test 11:** Pagination consistency (offset and limit work correctly)

Tests 6-10 behave the same in both versions: every returned activity matches the filter and the sample is among them; a non-matching filter returns an empty list.

**Endpoints:**

- `GET /ca/{API_VERSION}/activities/count`
- `GET /ca/{API_VERSION}/activities`
- `GET /ca/{API_VERSION}/activities?offset={offset}&limit={limit}`
- `GET /ca/v2/activities?areaId={areaId}`
- `GET /ca/v2/activities?platformId={platformId}`
- `GET /ca/v2/activities?createdAtFrom={datetime}&createdAtTo={datetime}`
- `GET /ca/v2/activities/count?areaId={areaId}`

---

### `test-str`

Test STR (Short-Term Rental) platform endpoints.

**Scripts:** `test_str_areas.py`, `test_str_listings.py`, `test_str_activities.py`

---

**`test_str_areas.py`**

**Setup:** Creates 5 fixture areas via the CA API before running tests.

**Tests:**

- **Test 1:** Count areas (`GET /str/areas/count`) - expects at least 5 (fixture count)
- **Test 2:** GET all areas and extract area IDs for subsequent tests
- **Test 3:** GET areas with pagination (offset=0, limit=1) - expects exactly 1 result
- **Test 4:** Verify response structure (areaId, competentAuthorityId, competentAuthorityName, filename, createdAt)
- **Test 5:** GET specific area by areaId (returns shapefile as `application/zip` with `Content-Disposition: attachment`)
- **Test 6:** GET another area by areaId
- **Test 7:** GET non-existent area (should return 404)
- **Test 8:** Verify Content-Disposition header contains filename

**Endpoints:**

- `GET /str/areas/count`
- `GET /str/areas`
- `GET /str/areas?offset={offset}&limit={limit}`
- `GET /str/areas/{areaId}` - Downloads shapefile

**Response Formats:**

- List endpoints: `application/json`
- Download endpoint: `application/zip` with `Content-Disposition: attachment`

---

**`test_str_listings.py`**

**Setup:** Creates two fixture areas via the CA API (`CA1_*` credentials): one that is regulated for listings, one that is regulated for activities only.

**Tests:**

- **Test 1:** POST listings/bulk with three areas: one valid, one that is regulated for activities only, one unknown → 200, per item OK, `regulation_error`, `not_found_error`
- **Test 2:** Resubmitting a pending listing is a correction → 201 with a new `createdAt`
- **Test 3:** GET listings and listings/count in the flagged scope (empty result is valid, count matches list length, one page, max 1000)
- **Test 4:** Acknowledging an unknown listing → 422 `not_found_error`
- **Test 5:** An empty batch → 422
- **Test 6:** A non-UTC `createdAtFrom` filter → 400

**Endpoints:** `POST /api/str/v2/listings/bulk`, `GET /api/str/v2/listings`, `GET /api/str/v2/listings/count`, `POST /api/str/v2/listing-acknowledgements/bulk`

**Authentication:** Requires STR client credentials (token loaded from `./tmp/.bearer_token`)

---

**`test_str_activities.py`**

**Setup:** Creates 3 fixture areas via the CA API before running tests.

**Tests:**

- **Test 1:** POST bulk activities (all valid) → 201, succeeded=2, failed=0
- **Test 2:** POST bulk activities (partial success) → 200, succeeded=1, failed=1
- **Test 3:** POST bulk activities (all invalid) → 422, succeeded=0, failed=2
- **Test 4:** POST bulk without authentication → 401
- **Test 5:** Stacked insert + cancel - POST `activityId=X` (default `status=finished`) then re-POST the same `activityId` with `status=cancelled`; the CA-side activity count stays the same because the cancellation is a new version of the same functional activity, not an additional current activity

**Endpoints:**

- `POST /api/str/{API_VERSION}/activities/bulk`

**Content-Type (POST):** `application/json`

**Authentication:** Requires STR client credentials (token loaded from `./tmp/.bearer_token`)

**HTTP Status Codes:**

- `201 Created` - All activities successfully created
- `200 OK` - Partial success (some OK, some NOK)
- `401 Unauthorized` - No/invalid authentication
- `422 Unprocessable Content` - All activities failed validation

**Response format:** `{ totalReceived, succeeded, failed, results: [{ activityIndex, activityId, status, activity?, errorMessages? }] }`
Where `results[].status` is the batch processing status (`OK`/`NOK`) and `results[].activity.status` is the activity lifecycle status (`finished`/`cancelled`).

---

### `test-sta`

Test STA (statistics authority) endpoints.

**Scripts:** `test_sta_listings.py`, `test_sta_activities.py`

---

**`test_sta_listings.py`**

**Tests:**

- **Test 1:** Count listings (`GET /sta/v2/listings/count`)
- **Test 2:** Get listings with `limit=1`
- **Test 3:** Every listing carries the listing fields
- **Test 4:** Filters narrow the result (`areaId`, `flags`, `createdAtFrom`/`createdAtTo` from a sample), `/count` matches the filtered list length (one page, max 1000)
- **Test 5:** An unknown flag code → 400
- **Test 6:** POST is rejected with `405 Method Not Allowed`
- **Test 7:** Role isolation - a CA token gets `403 Forbidden`. Requires `CA1_CLIENT_ID`/`CA1_CLIENT_SECRET`; skipped otherwise.

Tests 3-4 discover a sample listing (`?limit=1`); with no data they pass with a note.

**Endpoints:** `GET /sta/v2/listings`, `GET /sta/v2/listings/count`

---

**`test_sta_activities.py`**

**Tests:**

- **Test 1:** Count activities (`GET /sta/v1/activities/count`)
- **Test 2:** Get all activities across all competent authorities
- **Test 3:** Pagination (offset=0, limit=1)
- **Test 4:** Verify response structure contains the required STA fields (temporal, numberOfGuests, countryOfGuests, registrationNumber, competentAuthorityId)
- **Test 5:** POST is rejected with `405 Method Not Allowed` (read-only API)
- **Test 6:** Role isolation - a CA token gets `403 Forbidden` on the STA API. Requires `CA1_CLIENT_ID`/`CA1_CLIENT_SECRET`; skipped otherwise.
- **Test 7:** Filter by `areaId`
- **Test 8:** Filter by `platformId`
- **Test 9:** Filter by `competentAuthorityId`
- **Test 10:** Filter by `createdAtFrom` / `createdAtTo` (both equal to the sample's `createdAt`)
- **Test 11:** Non-matching `areaId` filter returns an empty list
- **Test 12:** `/count` with filter matches the length of the filtered list (one page, max 1000)

`make test-sta` runs this script once per version (v1, v2, see [API versions](#api-versions)); both versions serve the same activity endpoints. Tests 7-12 discover a sample activity (`?limit=1`) and derive the filter values from it; with no data they pass with a note. Every returned activity must match the filter and the sample must be among them.

**Endpoints:**

- `GET /sta/v1/activities/count`
- `GET /sta/v1/activities`
- `GET /sta/v1/activities?offset={offset}&limit={limit}`
- `GET /sta/v1/activities?areaId={areaId}`
- `GET /sta/v1/activities?platformId={platformId}`
- `GET /sta/v1/activities?competentAuthorityId={competentAuthorityId}`
- `GET /sta/v1/activities?createdAtFrom={datetime}&createdAtTo={datetime}`
- `GET /sta/v1/activities/count?areaId={areaId}`

**Authentication:** Requires STA client credentials (token loaded from `./tmp/.bearer_token`)

**HTTP Status Codes:**

- `200 OK` - Activities returned
- `401 Unauthorized` - No/invalid authentication
- `403 Forbidden` - Token lacks the `sdep_sta` or `sdep_read` role
- `405 Method Not Allowed` - Write method on the read-only API

---

### `test-lsa`

Test LSA (listing screening authority) endpoints and the whole listing lifecycle (random checks).

**Scripts:** `test_lsa_listings.py`

**Setup:** Creates a fixture area that is regulated for listings, via the CA API. Authenticates the other audiences with the `STR_*`, `CA1_*`, `LMA_*` and `STA_*` credentials.

**Tests:**

- **Test 1:** STR submits two listings (`POST /str/v2/listings/bulk`) → 201, both `pending`
- **Test 2:** LSA sees the pending listings (`GET /lsa/v2/listings?areaId`, `/count?areaId&platformId`)
- **Test 3:** LSA screens them (`POST /lsa/v2/listing-screenings/bulk`) → 201, one `flagged`, one `clear`
- **Test 4:** The LSA queue for the area is empty
- **Test 5:** STR sees only the flagged listing (`GET /str/v2/listings?areaId`)
- **Test 6:** STR acknowledges it (`POST /str/v2/listing-acknowledgements/bulk`) → 201; a retry → 422 `conflict_error`
- **Test 7:** CA sees the acknowledged listing in its area (`GET /ca/v2/listings?areaId&flags=UNK,EXP`)
- **Test 8:** LMA and STA see both listings; `status=clear` narrows to one
- **Test 9:** A stale version token is refused → 422 `conflict_error` with `loc` `["createdAt"]`
- **Test 10:** Role isolation - an STR token gets `403 Forbidden` on the LSA API

**Endpoints:** `GET /lsa/v2/listings`, `GET /lsa/v2/listings/count`, `POST /lsa/v2/listing-screenings/bulk`, plus the STR, CA, LMA and STA listing endpoints

**Authentication:** Requires LSA client credentials (token loaded from `./tmp/.bearer_token`) and the STR, CA1, LMA and STA client credentials from the environment

---

### `test-lma`

Test LMA (listing monitoring authority) endpoints.

**Scripts:** `test_lma_listings.py` - the same tests as `test_sta_listings.py`, against `GET /lma/v2/listings` and `GET /lma/v2/listings/count`; `test_reference_data.py`, see below

**Authentication:** Requires LMA client credentials (token loaded from `./tmp/.bearer_token`)

---

### `test-ama`

Test AMA (activity monitoring authority) endpoints.

**Scripts:** `test_ama_activities.py` - the same tests as `test_sta_activities.py`, against `GET /ama/v1/activities` and `GET /ama/v1/activities/count`; `test_reference_data.py`

**`test_reference_data.py`**

Also run by `test-ca`, `test-sta`, `test-lsa` and `test-lma`. The domain comes from the audience role in the bearer token (e.g. `sdep_ama`), so the script needs no extra variable. A domain version that does not serve the reference data fails, so [`tests/suites.txt`](../tests/suites.txt) only lists the versions that serve it: CA v2, STA v1 and v2, LSA v2, LMA v2, AMA v1.

**What it tests:**

- `GET /platforms`, `GET /competent-authorities`, `GET /areas`: `/count` and the list agree
- `GET /platforms/{id}`, `GET /competent-authorities/{id}` and `GET /areas/{id}` are not served (404), also not for a listed ID
- CA v2: platforms only, `GET /competent-authorities` returns 404

**Authentication:** Requires AMA client credentials (token loaded from `./tmp/.bearer_token`)

---

### `test-security`

Test security (headers, unauthorized, credentials).

**Scripts:** `test_auth_headers.py`, `test_auth_unauthorized.py`, `test_auth_client_secret.py`, `test_auth_client_jwt.py`, `test_client_id_regex.py`

---

**`test_auth_headers.py`**

**What it tests:**

- OWASP security headers (Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy, Cross-Origin-Embedder-Policy)
- CSP policy directives (default-src, script-src, frame-ancestors, object-src, unsafe-eval absence)
- Cache control on sensitive endpoints (no-store, Pragma no-cache)
- HSTS (`Strict-Transport-Security`) set by the application as defense in depth, next to any header set by the reverse proxy

**Endpoints tested:**

- `/` - Root endpoint
- `/api/health` - Health check
- `/api/ping` - Ping endpoint
- `/api/ca/{API_VERSION}/openapi.json` and `/api/ca/{API_VERSION}/docs` - OpenAPI document and Swagger UI; the version comes from `API_VERSION`, so one run covers one CA version

---

**`test_auth_unauthorized.py`**

**What it tests:**

- All secured endpoints return `401 Unauthorized` without authentication token
- Public endpoints (like `/api/health`) are excluded from this test

**Endpoints tested:**

Areas and activities:

- `GET /api/ping`
- `GET /api/str/v1/areas`, `GET /api/str/v1/areas/count`, `GET /api/str/v1/areas/{areaId}`
- `GET /api/str/v2/areas`, `GET /api/str/v2/areas/count`, `GET /api/str/v2/areas/{areaId}`
- `POST /api/str/v1/activities/bulk`, `POST /api/str/v2/activities/bulk`
- `POST /api/ca/v1/areas`, `POST /api/ca/v2/areas`
- `GET /api/ca/v1/areas`, `GET /api/ca/v1/areas/count`, `GET /api/ca/v1/areas/{areaId}`
- `GET /api/ca/v2/areas`, `GET /api/ca/v2/areas/count`, `GET /api/ca/v2/areas/{areaId}`
- `DELETE /api/ca/v1/areas/{areaId}`, `DELETE /api/ca/v2/areas/{areaId}`
- `GET /api/ca/v1/activities`, `GET /api/ca/v1/activities/count`
- `GET /api/ca/v2/activities`, `GET /api/ca/v2/activities/count`
- `GET /api/sta/v1/activities`, `GET /api/sta/v1/activities/count`
- `GET /api/sta/v2/activities`, `GET /api/sta/v2/activities/count`
- `GET /api/ama/v1/activities`, `GET /api/ama/v1/activities/count`

Listings (random checks):

- `POST /api/str/v2/listings/bulk`, `POST /api/str/v2/listing-acknowledgements/bulk`
- `GET /api/str/v2/listings`, `GET /api/str/v2/listings/count`
- `POST /api/lsa/v2/listing-screenings/bulk`
- `GET /api/lsa/v2/listings`, `GET /api/lsa/v2/listings/count`
- `GET /api/ca/v2/listings`, `GET /api/ca/v2/listings/count`
- `GET /api/lma/v2/listings`, `GET /api/lma/v2/listings/count`
- `GET /api/sta/v2/listings`, `GET /api/sta/v2/listings/count`

Reference data (`areas`, `competent-authorities`, `platforms`, each with `/count`):

- `GET /api/sta/v1/...`, `GET /api/sta/v2/...`
- `GET /api/lsa/v2/...`, `GET /api/lma/v2/...`, `GET /api/ama/v1/...`
- `GET /api/ca/v2/platforms`, `GET /api/ca/v2/platforms/count`

---

**`test_auth_client_secret.py`**

**What it tests:**

- STR platform client credentials authentication
- CA (Competent Authority) client credentials authentication
- JWT token acquisition and decoding
- Token payload inspection

**Required environment variables:**

- `BACKEND_BASE_URL`
- `CLIENT_SECRET_AUTH_ENABLED=true` on the backend under test
- `STR_CLIENT_ID`, `STR_CLIENT_SECRET`
- `CA1_CLIENT_ID`, `CA1_CLIENT_SECRET`

---

**`test_auth_client_jwt.py`**

**What it tests:**

- Client-signed-JWT (`private_key_jwt`) token acquisition end to end, for all six generated clients (`sdep-test-ca.jwt`, `sdep-test-str.jwt`, `sdep-test-sta.jwt`, `sdep-test-lsa.jwt`, `sdep-test-lma.jwt`, `sdep-test-ama.jwt`)
- Signs a short-lived assertion with each client's generated local private key in `tmp/<client-id>.private.pem` and exchanges it for a bearer token via `/api/auth/v1/token`
- Exercises the clients provisioned from the extended machine-client YAML with the matching public keys
- Role enforcement: each acquired token is used against every role's read-only count endpoint, expecting `200` for its own role and `403` for the other five

**Tests (per client):**

- **Test 1:** Acquire a bearer token with a client-signed JWT
- **Test 2:** Call the client's own role endpoint → `200`
- **Test 3-7:** Call the other five roles' endpoints → `403`

The role endpoint per client:

| Client              | Role | Endpoint                                  |
| ------------------- | ---- | ----------------------------------------- |
| `sdep-test-ca.jwt`  | CA   | `GET /api/ca/{version}/areas/count`       |
| `sdep-test-str.jwt` | STR  | `GET /api/str/{version}/areas/count`      |
| `sdep-test-sta.jwt` | STA  | `GET /api/sta/{version}/activities/count` |
| `sdep-test-lsa.jwt` | LSA  | `GET /api/lsa/v2/listings/count`          |
| `sdep-test-lma.jwt` | LMA  | `GET /api/lma/v2/listings/count`          |
| `sdep-test-ama.jwt` | AMA  | `GET /api/ama/{version}/activities/count` |

Only read-only count endpoints are used, so the test creates no data and is idempotent.

**Required environment variables:**

- `BACKEND_BASE_URL`
- `BACKEND_KC_BASE_URL` (the Keycloak URL the backend forwards to; falls back to `KC_BASE_URL`) - used to derive the assertion audience when `CLIENT_SIGNED_JWT_AUDIENCE` is not set
- Optional: `CLIENT_SIGNED_JWT_AUDIENCE`, `JWT_PROVISION_CLIENTS` (default `false`), `JWT_KEY_DIR` (default `tmp`), `JWT_CLIENT_IDS` (comma-separated subset, default all six), `KC_REALM`, `API_VERSION`

**Reuse in deployed environments:**

This suite can also be run in deployed environments that declare a client-signed-JWT test client, passing `JWT_CLIENT_IDS`, `JWT_KEY_DIR` and `CLIENT_SIGNED_JWT_AUDIENCE`.

Two settings make that possible:

- `JWT_PROVISION_CLIENTS` defaults to `false`. When `true` (set by `make test-security` for the local stack) the test first runs `make keycloak-configure`, which re-creates the machine clients from locally generated key pairs - correct locally, destructive against a deployed Keycloak
- `CLIENT_SIGNED_JWT_AUDIENCE` overrides the derived audience. Deployed environments must set it: Keycloak validates the assertion `aud` against its public issuer URL, which is neither the admin URL nor the in-cluster URL the backend forwards to

---

**`test_client_id_regex.py`**

**What it tests:**

- The default client-ID regex in `keycloak/add-realm-machine-clients.sh` accepts valid client IDs (`sdep.client_1`, `abc-123`, `a.b-c_d`) and rejects IDs containing a literal backslash
- Reads the regex straight from the shell script, so the test tracks the value actually used to provision machine clients

The regex is applied by bash `[[ =~ ]]`, which uses POSIX ERE. There, a backslash inside a bracket expression is a literal character, so writing the character class as `[A-Za-z0-9._\-]` would silently admit backslashes into client IDs. Python's `re` disagrees on exactly that point, so the test translates the pattern to bash semantics before matching - matching with plain `re.search` would not detect the flaw.

This test needs no running stack and no credentials: it is a static check of a shell script.

---

### `test-migrations`

Test Alembic migrations against a real PostgreSQL instance (started automatically when not in CI). Lives in the Makefile's Tests (migrations) section.

**Script:** `tests/test_postgres_check_constraints.py`

**What it tests:**

- All migrations apply cleanly (`make -C backend upgrade`) and the schema lands on the expected Alembic head revision
- The `CHECK` constraints in the resulting schema actually reject invalid rows, by inserting seed data and asserting the database raises an integrity error

Connects to PostgreSQL directly (SQLAlchemy); does not go through the HTTP API. Idempotent - it removes its own `sdep-test-*` seed rows before each run.

**Required environment variables:**

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB_NAME`, `POSTGRES_DB_USER`, `POSTGRES_DB_PASSWORD` (exported by the Makefile)

---

### `test-malware`

Test malware scanning against a real local ClamAV daemon. Requires ClamAV service (started automatically when not in CI). Lives in the Makefile's Tests (security) section, alongside `test-cve`.

**Script:** `tests/malware/test_malware_scan.py`

**What it tests:**

- ClamAV daemon reachability - pings ClamAV at `MALWARE_SCAN_CLAMAV_HOST:MALWARE_SCAN_CLAMAV_PORT` and waits up to `MALWARE_SCAN_CLAMAV_READY_TIMEOUT_SECONDS` for it to come up
- Clean payload → `passed_malware_scan = True`
- EICAR test payload → `passed_malware_scan = False` (signature is detected)

Exercises the backend's `app.security.malware_scan` module directly (loaded via `importlib`); does not go through the HTTP API.

**Required environment variables:**

- `MALWARE_SCAN_CLAMAV_HOST` (defaults to `localhost`)
- `MALWARE_SCAN_CLAMAV_PORT` (read from backend settings)
- `MALWARE_SCAN_CLAMAV_READY_TIMEOUT_SECONDS` (defaults to `180`)

---

## Helper scripts

### `test_auth_client_bootstrap.py`

**Purpose:** Utility script to authenticate and save bearer token

**What it does:**

- Performs the OAuth 2.0 Client Credentials flow with client-secret authentication
- Requests access token from `/api/auth/{API_VERSION}/token`
- Saves token to `./tmp/.bearer_token` for use by other scripts
- Used as a prerequisite for authenticated endpoint tests

**Required environment variables:**

- `BACKEND_BASE_URL` - API base URL
- `CLIENT_ID` - OAuth 2.0 client ID
- `CLIENT_SECRET` - OAuth 2.0 client secret; requires
  `CLIENT_SECRET_AUTH_ENABLED=true` on the backend under test
- `API_VERSION` (optional, defaults to `v1`)

---

### `test_health_ping.py`

**Purpose:** Basic API availability test

**What it tests:**

- Ping endpoint responds with HTTP 200 and `{"status":"OK"}`
- Supports both authenticated (with `BEARER_TOKEN`) and unauthenticated requests
- Automatically loads token from `./tmp/.bearer_token` if `BEARER_TOKEN` is not set

---

### `lib/create_fixture_areas.py`

**Purpose:** Create fixture areas for test isolation

**Usage:** `create_fixture_areas.py [count] [prefix] [regulation]`

**What it does:**

- Authenticates using CA client-secret flow with credentials (`CA1_CLIENT_ID`,
  `CA1_CLIENT_SECRET`); requires `CLIENT_SECRET_AUTH_ENABLED=true` on the
  backend under test
- Creates `count` areas (default: 3) with `prefix`-prefixed IDs via individual `POST /ca/areas` requests, optionally with a `regulation` (`listing`, `activity`, `all`)
- Uploads `test-data/shapefiles/Amsterdam.zip` as multipart/form-data for each area
- Outputs created area IDs to stdout (one per line), errors to stderr
- Does not modify `./tmp/.bearer_token` (uses a local token variable)

**Used by:** `test_str_areas.py`, `test-perf` (root Makefile)
