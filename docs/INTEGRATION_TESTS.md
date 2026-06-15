<h1>Integration Test Scripts</h1>

The [../tests](../tests) directory contains shell scripts for integration testing the SDEP (Single Digital Entry Point) API endpoints.

These tests verify API functionality, authentication, authorization, and security compliance.

- [Running Tests](#running-tests)
- [Configuration](#configuration)
  - [Credentials](#credentials)
  - [Bearer Tokens](#bearer-tokens)
  - [Exit Codes](#exit-codes)
- [Coverage](#coverage)
  - [`test`](#test) - Test all (quiet)
  - [`test-keep`](#test-keep) - Test all (quiet, keep test data)
  - [`test-verbose`](#test-verbose) - Test all (verbose)
  - [`test-smoke`](#test-smoke) - Test smoke test endpoints
  - [`test-ca`](#test-ca) - Test CA endpoints
  - [`test-str`](#test-str) - Test STR endpoints
  - [`test-rep`](#test-rep) - Test REP endpoints
  - [`test-security`](#test-security) - Test security (headers, unauthorized, credentials)
  - [`test-malware`](#test-malware) - Test malware scanning
- [Helper Scripts](#helper-scripts)
  - [`test_auth_client.sh`](#test_auth_clientsh)
  - [`test_health_ping.sh`](#test_health_pingsh)
  - [`lib/create_fixture_areas.sh`](#libcreate_fixture_areassh)

## Running Tests

## See [../Makefile](../Makefile).

## Configuration

---

### Credentials

Default test clients are configured in Keycloak. The Makefile retrieves secrets dynamically via `get_client_secret`:

**Competent Authority (CA)**

- **Client ID:** `sdep-test-ca.01`
- **Roles:** `sdep_ca`, `sdep_write`, `sdep_read`
- **Can access:** CA endpoints

**STR Platform**

- **Client ID:** `sdep-test-str.01`
- **Roles:** `sdep_str`, `sdep_write`, `sdep_read`
- **Can access:** STR platform endpoints

**Reporting / Statistics Office (REP)**

- **Client ID:** `sdep-test-rep.01`
- **Roles:** `sdep_rep`, `sdep_read` (read-only, no write role)
- **Can access:** REP endpoints

---

### Bearer Tokens

- Tokens are saved to `./tmp/.bearer_token` by `test_auth_client.sh`
- Other scripts automatically load tokens from this file
- Token location is configurable via `TOKEN_FILE` environment variable

---

### Exit Codes

All test scripts follow standard Unix exit codes:

- `0` - All tests passed
- `1` - Test failed or error occurred

## Coverage

---

### `test`

Test all (quiet). Runs `test-verbose` and filters output to the results summary.

---

### `test-keep`

Test all (quiet, keep test data). Same as `test` but skips cleanup of `sdep-test-*` rows after the run.

---

### `test-verbose`

Test all (verbose). Runs all suites below via `scripts/run-tests.sh` with full output and PRE/POST row count isolation checks.

---

### `test-smoke`

Smoke test for audit-excluded endpoints (SKIP_PATHS).

**Script:** `test_smoketest.sh`

**What it tests:**

- All audit-excluded, unauthenticated endpoints return HTTP 200
- Safe for production: read-only, no authentication, no test data

**Endpoints tested:**

- `/` - Root endpoint
- `/api/docs` - Landing page
- `/api/health` - Health check
- `/api/auth/v1/openapi.json` - Auth OpenAPI spec
- `/api/auth/v1/docs` - Auth Swagger UI
- `/api/ca/v1/openapi.json` - CA OpenAPI spec (v1)
- `/api/ca/v1/docs` - CA Swagger UI (v1)
- `/api/ca/v2/openapi.json` - CA OpenAPI spec (v2, with activity filters)
- `/api/ca/v2/docs` - CA Swagger UI (v2)
- `/api/str/v1/openapi.json` - STR OpenAPI spec
- `/api/str/v1/docs` - STR Swagger UI

**Required environment variables:**

- `BACKEND_BASE_URL` - API base URL

---

### `test-ca`

Test CA (Competent Authority) endpoints.

**Scripts:** `test_ca_areas.sh`, `test_ca_activities.sh`

---

**`test_ca_areas.sh`**

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
- **Test 12:** Cross-CA isolation - two CAs POSTing the same `areaId` each keep their own area (regression guard for issue #141). Requires `CA2_CLIENT_ID`/`CA2_CLIENT_SECRET`; skipped otherwise.

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

**`test_ca_activities.sh`**

**Tests (v1 - `GET /api/ca/v1/activities`):**

- **Test 1:** Count activities (`GET /ca/v1/activities/count`)
- **Test 2:** Get all activities
- **Test 3:** Pagination (offset=0, limit=1)
- **Test 4:** Verify response structure (activityId, activityName, status, platformId, platformName, url, registrationNumber, address, temporal, areaId)
- **Test 5:** Verify pagination consistency (offset and limit produce different results)

**Tests (v2 - `GET /api/ca/v2/activities`, with filters):**

- **Test 6:** Filter by `filterAreaId`
- **Test 7:** Filter by `filterPlatformId`
- **Test 8:** Filter by `filterCreatedAtFrom` / `filterCreatedAtTo` date range
- **Test 9:** GET with non-matching filter (should return empty list)

**Endpoints:**

- `GET /ca/v1/activities/count`
- `GET /ca/v1/activities`
- `GET /ca/v1/activities?offset={offset}&limit={limit}`
- `GET /ca/v2/activities?filterAreaId={areaId}`
- `GET /ca/v2/activities?filterPlatformId={platformId}`
- `GET /ca/v2/activities?filterCreatedAtFrom={datetime}&filterCreatedAtTo={datetime}`
- `GET /ca/v2/activities/count?filterAreaId={areaId}`

---

### `test-str`

Test STR (Short-Term Rental) platform endpoints.

**Scripts:** `test_str_areas.sh`, `test_str_activities_bulk.py`

---

**`test_str_areas.sh`**

**Setup:** Creates 5 fixture areas via `lib/create_fixture_areas.sh` before running tests.

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

**`test_str_activities_bulk.py`**

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

### `test-rep`

Test REP (reporting / statistics office) endpoints.

**Scripts:** `test_rep_activities.py`

---

**`test_rep_activities.py`**

**Tests:**

- **Test 1:** Count activities (`GET /rep/v1/activities/count`)
- **Test 2:** Get all activities across all competent authorities
- **Test 3:** Pagination (offset=0, limit=1)
- **Test 4:** Verify response structure contains the acceptance-criteria fields of issue #99 (temporal, numberOfGuests, countryOfGuests, registrationNumber, competentAuthorityId)
- **Test 5:** POST is rejected with `405 Method Not Allowed` (read-only API)
- **Test 6:** Role isolation - a CA token gets `403 Forbidden` on the REP API. Requires `CA1_CLIENT_ID`/`CA1_CLIENT_SECRET`; skipped otherwise.

**Endpoints:**

- `GET /rep/v1/activities/count`
- `GET /rep/v1/activities`
- `GET /rep/v1/activities?offset={offset}&limit={limit}`

**Authentication:** Requires REP client credentials (token loaded from `./tmp/.bearer_token`)

**HTTP Status Codes:**

- `200 OK` - Activities returned
- `401 Unauthorized` - No/invalid authentication
- `403 Forbidden` - Token lacks the `sdep_rep` or `sdep_read` role
- `405 Method Not Allowed` - Write method on the read-only API

---

### `test-security`

Test security (headers, unauthorized, credentials).

**Scripts:** `test_auth_headers.sh`, `test_auth_unauthorized.sh`, `test_auth_credentials.sh`

---

**`test_auth_headers.sh`**

**What it tests:**

- OWASP security headers (Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy, Cross-Origin-Embedder-Policy)
- CSP policy directives (default-src, script-src, frame-ancestors, object-src, unsafe-eval absence)
- Cache control on sensitive endpoints (no-store, Pragma no-cache)
- HSTS delegation check (should be handled by reverse proxy, not application)

**Endpoints tested:**

- `/` - Root endpoint
- `/api/health` - Health check
- `/api/ping` - Ping endpoint
- `/api/ca/v1/openapi.json`, `/api/ca/v2/openapi.json` - OpenAPI specifications

---

**`test_auth_unauthorized.sh`**

**What it tests:**

- All secured endpoints return `401 Unauthorized` without authentication token
- Public endpoints (like `/api/health`) are excluded from this test

**Endpoints tested:**

- `GET /api/ping`
- `GET /api/str/v1/areas`
- `GET /api/str/v1/areas/count`
- `GET /api/str/v1/areas/amsterdam-area0363`
- `POST /api/str/v1/activities/bulk`
- `POST /api/ca/v1/areas`
- `GET /api/ca/v1/areas`
- `GET /api/ca/v1/areas/count`
- `GET /api/ca/v1/areas/{areaId}`
- `DELETE /api/ca/v1/areas/{areaId}`
- `GET /api/ca/v1/activities`
- `GET /api/ca/v1/activities/count`

---

**`test_auth_credentials.sh`**

**What it tests:**

- STR platform client credentials authentication
- CA (Competent Authority) client credentials authentication
- JWT token acquisition and decoding
- Token payload inspection

**Required environment variables:**

- `BACKEND_BASE_URL`
- `STR_CLIENT_ID`, `STR_CLIENT_SECRET`
- `CA1_CLIENT_ID`, `CA1_CLIENT_SECRET`

---

### `test-malware`

Test malware scanning against a real local ClamAV daemon. Requires ClamAV service (started automatically when not in CI).

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

## Helper Scripts

---

### `test_auth_client.sh`

**Purpose:** Utility script to authenticate and save bearer token

**What it does:**

- Performs OAuth2 client credentials flow
- Requests access token from `/api/auth/{API_VERSION}/token`
- Saves token to `./tmp/.bearer_token` for use by other scripts
- Used as a prerequisite for authenticated endpoint tests

**Required environment variables:**

- `BACKEND_BASE_URL` - API base URL
- `CLIENT_ID` - OAuth2 client ID
- `CLIENT_SECRET` - OAuth2 client secret
- `API_VERSION` (optional, defaults to `v1`)

---

### `test_health_ping.sh`

**Purpose:** Basic API availability test

**What it tests:**

- Ping endpoint responds with HTTP 200 and `{"status":"OK"}`
- Supports both authenticated (with `BEARER_TOKEN`) and unauthenticated requests
- Automatically loads token from `./tmp/.bearer_token` if `BEARER_TOKEN` is not set

---

### `lib/create_fixture_areas.sh`

**Purpose:** Create fixture areas for test isolation

**Usage:** `create_fixture_areas.sh [count] [prefix]`

**What it does:**

- Authenticates using CA client credentials (`CA1_CLIENT_ID`, `CA1_CLIENT_SECRET`)
- Creates `count` areas (default: 3) with `prefix`-prefixed IDs via individual `POST /ca/areas` requests
- Uploads `test-data/shapefiles/Amsterdam.zip` as multipart/form-data for each area
- Outputs created area IDs to stdout (one per line), errors to stderr
- Does not modify `./tmp/.bearer_token` (uses a local token variable)

**Used by:** `test_str_areas.sh`, `test-perf` (root Makefile)
