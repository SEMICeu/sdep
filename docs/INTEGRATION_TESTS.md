<h1>Integration Test Scripts</h1>

The [../tests](../tests) directory contains shell scripts for integration testing the SDEP (Single Digital Entry Point) API endpoints.

These tests verify API functionality, authentication, authorization, and security compliance.

- [Running Tests](#running-tests)
- [Test Scripts](#test-scripts)
  - [Authentication \& authorization tests](#authentication-authorization-tests)
    - [`test_auth_client.sh`](#test_auth_clientsh)
    - [`test_auth_credentials.sh`](#test_auth_credentialssh)
    - [`test_auth_headers.sh`](#test_auth_headerssh)
    - [`test_auth_unauthorized.sh`](#test_auth_unauthorizedsh)
  - [Healthcheck tests](#healthcheck-tests)
    - [`test_health_ping.sh`](#test_health_pingsh)
  - [Competent Authority (CA) tests](#competent-authority-ca-tests)
    - [`test_ca_areas.sh`](#test_ca_areassh)
    - [`test_ca_activities.sh`](#test_ca_activitiessh)
  - [Short-Term Rental (STR) Platform tests](#short-term-rental-str-platform-tests)
    - [`test_str_areas.sh`](#test_str_areassh)
    - [`test_str_activities_bulk.sh`](#test_str_activities_bulksh)
  - [Helper scripts](#helper-scripts)
    - [`lib/create_fixture_areas.sh`](#libcreate_fixture_areassh)
- [Configuration](#configuration)
  - [Credentials](#credentials)
  - [Bearer tokens](#bearer-tokens)
  - [Exit Codes](#exit-codes)


## Running Tests

See [../Makefile](../Makefile). Available targets:

| Target               | Description                                                            |
| -------------------- | ---------------------------------------------------------------------- |
| `make test`          | Run all tests (quiet, summary only)                                    |
| `make test-verbose`  | Run all tests with full output and PRE/POST row count isolation checks |
| `make test-security` | Run security tests only (headers, unauthorized, credentials)           |
| `make test-str`      | Run STR platform endpoint tests only                                   |
| `make test-ca`       | Run CA endpoint tests only                                             |

## Test Scripts

### Authentication & authorization tests

#### `test_auth_client.sh`
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

#### `test_auth_credentials.sh`
**Purpose:** Test OAuth2 token acquisition for both STR and CA clients

**What it tests:**
- STR platform client credentials authentication
- CA (Competent Authority) client credentials authentication
- JWT token acquisition and decoding
- Token payload inspection

**Required environment variables:**
- `BACKEND_BASE_URL`
- `STR_CLIENT_ID`, `STR_CLIENT_SECRET`
- `CA_CLIENT_ID`, `CA_CLIENT_SECRET`

#### `test_auth_headers.sh`
**Purpose:** Verify security headers compliance across multiple endpoints

**Endpoints tested:**
- `/` - Root endpoint
- `/api/health` - Health check
- `/api/ping` - Ping endpoint
- `/api/ca/{API_VERSION}/openapi.json` - OpenAPI specification

**What it tests:**
- OWASP security headers (Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy, Cross-Origin-Embedder-Policy)
- CSP policy directives (default-src, script-src, frame-ancestors, object-src, unsafe-eval absence)
- Cache control on sensitive endpoints (no-store, Pragma no-cache)
- HSTS delegation check (should be handled by reverse proxy, not application)

#### `test_auth_unauthorized.sh`
**Purpose:** Verify all secured endpoints properly reject unauthenticated requests

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

**What it tests:**
- All secured endpoints return `401 Unauthorized` without authentication token
- Public endpoints (like `/api/health`) are excluded from this test

---

### Healthcheck tests

#### `test_health_ping.sh`
**Purpose:** Basic API availability test

**What it tests:**
- Ping endpoint responds with HTTP 200 and `{"status":"OK"}`
- Supports both authenticated (with `BEARER_TOKEN`) and unauthenticated requests
- Automatically loads token from `./tmp/.bearer_token` if `BEARER_TOKEN` is not set

---

### Competent Authority (CA) tests

#### `test_ca_areas.sh`
**Purpose:** Test single area submission for competent authorities

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

#### `test_ca_activities.sh`
**Purpose:** Comprehensive testing of activity query endpoints for competent authorities

**Tests:**
- **Test 1:** Count activities (`GET /ca/activities/count`)
- **Test 2:** Get all activities
- **Test 3:** Pagination (offset=0, limit=1)
- **Test 4:** Verify response structure (activityId, activityName, status, platformId, platformName, url, registrationNumber, address, temporal, areaId)
- **Test 5:** GET specific activity by URL filter
- **Test 6:** GET activities filtered by areaId
- **Test 7:** GET with non-existent areaId (should return empty list or 404)
- **Test 8:** Verify pagination consistency (offset and limit produce different results)

**Endpoints:**
- `GET /ca/activities/count`
- `GET /ca/activities`
- `GET /ca/activities?url={url}`
- `GET /ca/activities?areaId={areaId}`
- `GET /ca/activities?offset={offset}&limit={limit}`

---

### Short-Term Rental (STR) Platform tests

#### `test_str_areas.sh`
**Purpose:** Comprehensive testing of area lookup endpoints for STR platforms

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

#### `test_str_activities_bulk.sh`
**Purpose:** Test bulk activity submission for STR platforms

**Setup:** Creates 3 fixture areas via `lib/create_fixture_areas.sh` before running tests.

**Tests:**
- **Test 1:** POST bulk activities (all valid) → 201, succeeded=2, failed=0
- **Test 2:** POST bulk activities (partial success) → 200, succeeded=1, failed=1
- **Test 3:** POST bulk activities (all invalid) → 422, succeeded=0, failed=2
- **Test 4:** POST bulk without authentication → 401

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

### Helper scripts

#### `lib/create_fixture_areas.sh`
**Purpose:** Create fixture areas for test isolation

**Usage:** `create_fixture_areas.sh [count] [prefix]`

**What it does:**
- Authenticates using CA client credentials (`CA_CLIENT_ID`, `CA_CLIENT_SECRET`)
- Creates `count` areas (default: 3) with `prefix`-prefixed IDs via individual `POST /ca/areas` requests
- Uploads `test-data/shapefiles/Amsterdam.zip` as multipart/form-data for each area
- Outputs created area IDs to stdout (one per line), errors to stderr
- Does not modify `./tmp/.bearer_token` (uses a local token variable)

**Used by:** `test_str_areas.sh`, `test_str_activities_bulk.sh`, `test-perf` (Makefile)

---

## Configuration

### Credentials

Default test clients are configured in Keycloak. The Makefile retrieves secrets dynamically via `get_client_secret`:

**Competent Authority (CA)**
- **Client ID:** `sdep-test-ca01`
- **Roles:** `sdep_ca`, `sdep_write`, `sdep_read`
- **Can access:** CA endpoints

**STR Platform**
- **Client ID:** `sdep-test-str01`
- **Roles:** `sdep_str`, `sdep_write`, `sdep_read`
- **Can access:** STR platform endpoints

---

### Bearer tokens

- Tokens are saved to `./tmp/.bearer_token` by `test_auth_client.sh`
- Other scripts automatically load tokens from this file
- Token location is configurable via `TOKEN_FILE` environment variable

---

### Exit Codes

All test scripts follow standard Unix exit codes:
- `0` - All tests passed
- `1` - Test failed or error occurred
