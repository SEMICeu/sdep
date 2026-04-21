<h1>Performance Tests</h1>

The [../tests/perf](../tests/perf) directory contains a [Locust](https://locust.io/) test for load testing the SDEP bulk activity endpoint (`POST /str/activities/bulk`).

- [Running Performance Tests](#running-performance-tests)
- [Implementation](#implementation)
  - [Locust test](#locust-test)
  - [Test data generation](#test-data-generation)
  - [Test data cleanup](#test-data-cleanup)
- [Results](#results)
- [Benchmarks](#benchmarks)
- [Database tuning](#database-tuning)
  - [Connection pool chain](#connection-pool-chain)
  - [SQLAlchemy pool (`backend/app/db/config.py`)](#sqlalchemy-pool-backendappdbconfigpy)
  - [PgBouncer pool (`sdep-cnpg Pooler` resource)](#pgbouncer-pool-sdep-cnpg-pooler-resource)
  - [Example: sizing for 50 concurrent users](#example-sizing-for-50-concurrent-users)
- [Network tuning](#network-tuning)
  - [Cause](#cause)
  - [Solution alternatives](#solution-alternatives)
  - [Recommendation](#recommendation)
- [Service Level Objectives (SLO)](#service-level-objectives-slo)
  - [Service Level Indicators (SLIs)](#service-level-indicators-slis)
  - [Strategies for bulk updates](#strategies-for-bulk-updates)
  - [Error budgets for batch processing](#error-budgets-for-batch-processing)
  - [Summary: SLI measurement gaps](#summary-sli-measurement-gaps)

## Running Performance Tests

See [../Makefile](../Makefile). The Makefile delegates to [../scripts/run-tests-perf.sh](../scripts/run-tests-perf.sh).

Quick reference:

| Target           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| `make test-perf` | Run bulk performance test with various configuration options |

## Implementation

The performance test consists of two files:

- [`scripts/run-tests-perf.sh`](../scripts/run-tests-perf.sh) orchestrates configuration, fixture setup, the Locust run, and cleanup
- [`tests/perf/locustfile.py`](../tests/perf/locustfile.py) contains the actual load test logic

Both are invoked via `make test-perf`.

### Locust test

`perf/locustfile.py`

**Purpose:** Load test the bulk activity endpoint (`POST /str/activities/bulk`) to measure throughput and validate capacity.

**Tooling:** [Locust](https://locust.io/) (Python-based load testing), installed on-demand via `uvx`.

**Design:**
- Authenticates via OAuth2 client credentials (same flow as integration tests)
- Generates realistic activity payloads with randomized addresses, guest counts, and country codes
- Submits batches via `POST /str/activities/bulk` at maximum throughput
- Collects per-request success/failure counts from the bulk response body
- Prints a summary with total activities, throughput (activities/sec), extrapolated capacity (activities/day), and comparison against the configured target

**How it works:**
1. Makefile creates fixture areas via `lib/create_fixture_areas.sh` (5 areas with `sdep-test-perf-*` IDs)
2. Spawns `PERF_USERS` concurrent Locust users (default: 10), ramping up at `PERF_RAMP_UP` users/second
3. Each Locust user authenticates at start and re-authenticates automatically when the bearer token expires (HTTP 401), then repeatedly submits bulk requests (0.1-0.5s pause between requests)
4. After the configured duration, Locust prints per-endpoint statistics and the custom summary block
5. Unless `PERF_KEEP_DATA=true`, the script runs `postgres/clean-testrun.sql` to remove all test data from the database

**Note on wait time and measurements:** The 0.1–0.5s pause between requests (Locust `wait_time`) adds to the total wall-clock duration but does **not** affect per-request response time statistics (avg, p50, p95, p99). It does slightly reduce measured throughput (activities/sec) compared to a zero-wait scenario, because each user idles between requests.

### Test data generation

No fixture files are used - all test data is generated at runtime by `_generate_activity()` in `locustfile.py`. Each Locust task iteration generates `PERF_BATCH_SIZE` activities (default: 500) per HTTP request.

Each activity contains the following fields:

| Field                | How it is generated                                                                                                                       |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `activityId`         | Prefix + 12 random hex characters from `uuid4`. Prefix is `sdep-test-perf-` (throwaway) or `perf-` when `PERF_KEEP_DATA=true`             |
| `url`                | Fake URL using the same unique ID (e.g. `http://sdep-test-perf.example.com/<id>`)                                                         |
| `registrationNumber` | `REGPERF` + 8 uppercase hex characters                                                                                                    |
| `address`            | Random Dutch street name (`Prinsengracht`, `Keizersgracht`, etc.), house number (1–999), postcode, and city from hardcoded lists          |
| `temporal`           | `startDatetime` = current UTC timestamp; `endDatetime` = fixed (`2027-12-31T23:59:59Z`)                                                   |
| `areaId`             | Randomly picked from `PERF_AREA_IDS` (created by the Makefile via `lib/create_fixture_areas.sh`)                                          |
| `numberOfGuests`     | Random integer 1–10                                                                                                                       |
| `countryOfGuests`    | List of length `numberOfGuests`, each element sampled with replacement from `NLD`, `DEU`, `BEL`, `FRA`, `GBR`, `ESP`, `ITA`, `USA`, `N/A` |

The `activityId` prefix convention controls cleanup:

- IDs starting with `sdep-test-perf-` are treated as throwaway test data and cleaned up after the test run
- When `PERF_KEEP_DATA=true`, the prefix is `perf-` and data is retained in the database.

### Test data cleanup

After the Locust run completes, `scripts/run-tests-perf.sh` automatically cleans up test data unless `PERF_KEEP_DATA=true`.

Cleanup executes `postgres/clean-testrun.sql` via `docker exec psql`, which:

1. **Deletes activities** in batches of 10,000 rows where `activity_id LIKE 'sdep-test-%'` or the activity belongs to an area matching `sdep-test-%`. Batched deletes avoid long-running transactions that could time out under load.
2. **Deletes areas** linked to `sdep-test-%` area IDs or `sdep-test-%` competent authorities.
3. **Deletes platforms** with `sdep-test-%` platform IDs.
4. **Deletes competent authorities** with `sdep-test-%` IDs.

Deletion follows FK order: children (activities) first, then parents (areas, platforms, competent authorities).

The same cleanup SQL is used by `make .clean-testrun` for all test types (integration and performance), since all test data shares the `sdep-test-*` naming convention.

- When `PERF_KEEP_DATA=true`, the activity ID prefix switches to `perf-` (without the `sdep-test-` prefix)
- So those records are not matched by the cleanup query and survive in the database

## Results

After running the tests:

| Field                          | Meaning                                                                                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Configuration**              | Repeats the parameter values used for this test run                                                                                                          |
| **Total activities processed** | Sum of all per-item OK + NOK results across all HTTP requests, incl. overshoot                                                                               |
| **HTTP requests**              | Total HTTP requests with per-endpoint breakdown (auth + bulk)                                                                                                |
| **Throughput**                 | Actual sustained rate of successfully processed activities per second                                                                                        |
| **Bulk requests/sec**          | Actual sustained rate of bulk POST requests per second (x activities per request)                                                                            |
| **Extrapolated**               | Throughput projected over 24 hours - what the system *can* sustain                                                                                           |
| **Target**                     | What you *asked* for (`PERF_ACTIVITIES_TARGET`), reached by `PERF_USERS` concurrent users                                                                    |
| **Verdict**                    | Whether extrapolated capacity meets or exceeds the target, with the headroom ratio                                                                           |
| **Overshoot**                  | Only shown when `PERF_STOP_ON_TARGET=true` and total exceeds target (see explanation below)                                                                  |
| **Correctness (SLI)**          | Post-test verification: samples 10 submitted activities and verifies them via `GET /ca/activities` (only runs when `PERF_KEEP_DATA=true`; skipped otherwise) |

**Note on target vs extrapolated:** The target controls the *minimum* load (number of concurrent users). Each user fires requests as fast as possible, so actual throughput is whatever the server can sustain. The "extrapolated" value shows real capacity; the ratio tells you how much headroom exists above the target.

**Note on overshoot when `PERF_STOP_ON_TARGET=true`:** When the target is reached, the test signals Locust to stop. However, all concurrent users have already sent their current request, and those in-flight requests complete at the database level even though their responses may not be counted by Locust. The summary shows two overshoot values:
- **Overshoot (counted):** extra activities recorded in Locust's counter beyond the target (may be 0 if the runner shut down before counting the last responses)
- **Overshoot (max):** worst-case overshoot = `PERF_USERS x PERF_BATCH_SIZE` (e.g. 10 users x 1000 batch = 10,000 activities)

The actual database row count may be higher than what Locust reports. This is inherent to concurrent load testing - `runner.quit()` cannot cancel in-flight HTTP requests.

**Note on `PERF_RAMP_UP`:** Controls how many users are spawned per second (Locust's `-r` flag). Default is `1` (one user per second). With 10 users and ramp-up 1, all users are active within 10 seconds - fast enough for most tests while giving the system time to handle each user's authentication request sequentially. For stress testing with 100+ users, keeping ramp-up at 1/sec is important to avoid overwhelming the auth endpoint at startup. Set to a higher value (e.g. `PERF_RAMP_UP=10`) to spawn all users instantly.

## Benchmarks

Industry-standard benchmarks for API response times:

| Response time | Rating                     |
| ------------- | -------------------------- |
| < 100 ms      | Excellent (fast endpoints) |
| 100-300 ms    | Very good (typical APIs)   |
| 300-500 ms    | Acceptable                 |
| > 1 s         | Noticeable delay           |

**References:**
- Google SRE Workbook (Latency & SLOs)
- AWS Well-Architected Framework (Performance Efficiency)
- Nielsen Norman Group - [Response Time Limits](https://www.nngroup.com/articles/response-times-3-important-limits/)

**Contextualisation for bulk endpoints:**

- These benchmarks are based on individual HTTP requests
- When assessing bulk performance, consider both the per-request latency and the per-item cost (i.e., response time divided by batch size)
- For example, processing up to 1000 activities in a single request: a 200 ms response time equates to 0.2 ms per item (excellent), whereas 200 ms for a single-item endpoint would be considered only “very good”

## Database tuning

### Connection pool chain

Requests flow through two connection pools before reaching PostgreSQL:

```
Locust users ─► sdep-backend (SQLAlchemy pool) ─► PgBouncer ─► PostgreSQL
```

Both pools must be sized correctly. If the SQLAlchemy pool is too small, requests queue inside the backend waiting for a database connection - even though PgBouncer and PostgreSQL have plenty of capacity.

### SQLAlchemy pool (`backend/app/db/config.py`)

| Parameter      | Description                                                    |
| -------------- | -------------------------------------------------------------- |
| `pool_size`    | Number of persistent connections kept open                     |
| `max_overflow` | Extra connections created on demand when `pool_size` is full   |
| **Total**      | `pool_size + max_overflow` = maximum concurrent DB connections |

The pool must accommodate the number of concurrent requests the backend handles. Each bulk request holds a connection for the duration of its database transaction - which can be several seconds under load. If all connections are in use, new requests wait up to 30 seconds and then fail with:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size N overflow M reached, connection timed out
```

**Sizing rule:** `pool_size + max_overflow` should be at least as large as the expected number of concurrent bulk requests, but must stay within PgBouncer's `default_pool_size` budget. With multiple backend replicas, divide the budget accordingly (e.g. 2 replicas with PgBouncer pool of 50 → 25 max connections per replica).

### PgBouncer pool (`sdep-cnpg Pooler` resource)

| Parameter           | Description                                                       |
| ------------------- | ----------------------------------------------------------------- |
| `default_pool_size` | Max server connections per user/database pair                     |
| `max_client_conn`   | Max client connections PgBouncer accepts (from all backend pods)  |
| `reserve_pool_size` | Extra connections available when the regular pool is fully in use |

PgBouncer sits between the backend and PostgreSQL. Its `default_pool_size` is the upper bound for how many connections all backend replicas combined can use simultaneously.

### Example: sizing for 50 concurrent users

| Layer      | Parameter           | Value | Rationale                                     |
| ---------- | ------------------- | ----- | --------------------------------------------- |
| SQLAlchemy | `pool_size`         | 20    | Persistent connections for steady-state load  |
| SQLAlchemy | `max_overflow`      | 30    | Burst capacity for peak load                  |
| SQLAlchemy | **total**           | 50    | Matches PgBouncer budget for a single replica |
| PgBouncer  | `default_pool_size` | 50    | Allows 50 concurrent server connections       |
| PgBouncer  | `max_client_conn`   | 1000  | Headroom for connection churn                 |

If you scale to 2 backend replicas, set SQLAlchemy to `pool_size=10, max_overflow=15` (25 per replica × 2 = 50 total ≤ PgBouncer's 50).

## Network tuning

Under sustained load, a small percentage of HTTP requests may fail with connection-level errors (`RemoteDisconnected`, `ChunkedEncodingError`) even though the backend processed the request successfully (HTTP 201). These are not application errors - they are TCP connection drops between the client and the backend, caused by intermediate network components (reverse proxy, load balancer) closing the connection before the client reads the full response.

### Cause

The request path typically passes through multiple network layers:

```
Client ─► TCP load balancer (e.g. HAProxy) ─► TLS/reverse proxy (e.g. nginx-ingress) ─► Backend
```

Each layer enforces its own timeouts. A bulk request that takes several seconds under load can exceed these timeouts, causing the connection to be closed mid-response:

- **TLS/reverse proxy (nginx-ingress):** `proxy-read-timeout` defaults to 60s
  - Bulk requests with large batches under peak load can approach or exceed this
- **TCP load balancer (HAProxy):** `timeout http-request` (time to receive the full request headers) and `timeout server` (time to wait for the backend response) can also drop connections
  - For example, `timeout http-request 10s` may be too aggressive for large payloads that are slow to transmit

### Solution alternatives

1. **Client-side retry logic (implemented in the performance test)**

   The bulk activity endpoint is idempotent (re-submitting an `activityId` versions the previous record rather than creating a duplicate), so retrying on connection-level failures is safe. The Locust test retries up to 2 times with linear backoff (0.5s, 1.0s) when the response status code is 0 (connection failure). This handles transient network drops without requiring infrastructure changes.

2. **TLS/reverse proxy timeout (deployment concern, out of scope of this project)**

   Increase `proxy-read-timeout` to accommodate bulk request processing times. For example, in nginx-ingress:

   ```yaml
   # nginx-ingress annotation
   nginx.ingress.kubernetes.io/proxy-read-timeout: "300"   # 5 minutes
   ```

   This gives the backend enough time to process large batches without the reverse proxy closing the connection prematurely.

3. **TCP load balancer timeout (deployment concern, out of scope of this project)**

   Ensure the load balancer's server-side timeout is at least as large as the reverse proxy timeout. For example, in HAProxy:

   ```
   timeout http-request  30s    # time to receive full request headers
   timeout server        300s   # time to wait for backend response
   ```

   If `timeout http-request` is too low, large payloads transmitted over slow connections may be dropped before the backend even starts processing.

### Recommendation

Apply all three: client-side retry absorbs occasional hiccups regardless of infrastructure, while the proxy and load balancer timeouts prevent the hiccups from occurring in the first place. The proxy and load balancer changes are deployment-level configuration managed (out of scope of this project).


## Service Level Objectives (SLO)

When looking at approaches in public cloud, e.g. in Google SRE practice, SLOs for batch processing differ fundamentally from interactive services. Where request-driven services focus on *availability* and *latency*, batch SLOs revolve around data throughput and freshness.

### Service Level Indicators (SLIs)

Four SLIs are most relevant for bulk activity ingestion:

**A. Freshness**

Freshness measures how "stale" data is - the time between "data changed at source" and "data is available in our system". It is the most important SLI for systems that **pull** data on a schedule (e.g. a pipeline that polls an external source every 15 minutes).

SDEP is a **push API**: external STR platforms submit activities via HTTP whenever they choose, and the data is persisted within the same request. There is no scheduled pipeline, no polling interval, no batch window. The "freshness" is entirely controlled by the caller, not by SDEP. Any delay in data availability is already captured by the **throughput** and **latency** SLIs - if the system is too slow or backlogged, those metrics will show it.

- **Relevance to SDEP:** Low. Freshness is not a meaningful SLI for a push-based API.
- **Current coverage:** Not measured, and not needed.

**B. Coverage**

Batch processes can skip records due to corrupt data or configuration errors.

- **Definition:** The percentage of records successfully processed out of the total number of records submitted.
- **Example SLO:** At least 99.9% of submitted activities per day are successfully processed.
- **Current coverage:** Fully measured. The test reports a `Coverage (SLI)` percentage that combines all failure modes into a single number: `succeeded / (succeeded + nok + http_failures × batch_size)`. This accounts for application-level NOK items (validation failures, FK errors) as well as HTTP-level failures (502, connection reset) where the entire batch of `batch_size` activities is assumed lost.

**C. Correctness**

A bug in transformation logic can silently corrupt millions of records in a single batch run.

- **Definition:** The percentage of records where the output is valid according to defined business rules.
- **Measurement:** Typically done via "canary data" or integration tests that run alongside the pipeline.
- **Current coverage:** Measured. After the performance test completes, the test samples 10 submitted activities and verifies them via `GET /ca/activities` (using the CA client, since the STR client has no GET endpoint). For each sampled activity, it compares key fields (`url`, `areaId`, `registrationNumber`, `numberOfGuests`, `address.*`) against the originally submitted payload. Results are printed as `Correctness (SLI)` in the summary. This catches silent data corruption under load (e.g. race conditions, partial writes).

**D. Throughput**

Useful for systems with variable load to ensure the pipeline keeps up with growth.

- **Definition:** The number of records processed per unit of time.
- **Example SLO:** The pipeline processes at least 100,000 records per second during peak hours.
- **Current coverage:** Fully measured. This is the primary metric of the performance test: `Throughput` (activities/sec), `Bulk requests/sec`, and `Extrapolated` (activities/day). The `Verdict` line compares extrapolated capacity against the configured target.

### Strategies for bulk updates

Google applies specific patterns to guarantee reliability at large volumes. Here is how SDEP implements them:

| Strategy                    | Description                                                                       | SDEP implementation                                                                                                                                                                                                                              |
| --------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Atomicity**               | A batch request succeeds or fails as a whole, preventing partial states           | Each bulk request is a single database transaction. On error, the entire batch rolls back - no half-written state. Per-item validation failures are reported as NOK without aborting the valid items in the same batch.                          |
| **Idempotency**             | A bulk update can be retried without creating duplicates                          | Implemented via activity versioning: re-submitting an `activityId` marks the previous version as ended (`ended_at = now()`) and inserts a new current version. Duplicate `activityId` values within a single batch are deduplicated (last-wins). |
| **Side-by-side validation** | Compare output of a new batch version against the previous one before overwriting | Not currently implemented. Could be added as a post-ingestion step that compares record counts and checksums between the previous and current batch for a given platform.                                                                        |

### Error budgets for batch processing

Batch errors behave differently in an error budget than request-level errors:

- **Impact:** A single failing daily batch job can consume 100% of the daily error budget in one go - unlike interactive services where errors are distributed across many small requests.
- **Alerting:** Set alerts on "time-to-complete". If a batch job takes 2x longer than normal, this is often a precursor to an SLO breach.
- **SDEP relevance:** The performance test's `Verdict` line is essentially a throughput error budget check - if extrapolated capacity drops below the target, the system cannot sustain the required daily volume. The `10 consecutive failures` abort mechanism acts as an early warning: if the system is degraded enough to fail 10 requests in a row, the test stops rather than burning through the error budget.

### Summary: SLI measurement gaps

| SLI         | Measured by perf test?                                             | Suggested extension |
| ----------- | ------------------------------------------------------------------ | ------------------- |
| Freshness   | N/A - not meaningful for a push-based API                          | -                   |
| Coverage    | Yes - `Coverage (SLI)` in summary                                  | -                   |
| Correctness | Yes - `Correctness (SLI)` in summary (post-test sample-and-verify) | -                   |
| Throughput  | Yes                                                                | -                   |

---
*Based on the Google SRE Workbook & Google Cloud Architecture Framework.*
