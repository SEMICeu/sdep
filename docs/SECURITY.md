<h1>Security</h1>

## Authorization

### oAuth2

Adopted oAuth2 with JWT, which is the standard for trusted machine-to-machine (M2M) interaction.

https://datatracker.ietf.org/doc/html/rfc6749#section-4.4

### Smaller platforms

Smaller platforms can opt for delegating SDEP API-invocation to third-parties.

In such case, the platform arranges data submission with their party; the party becomes registered in SDEP.

## Audit log

To log "**who** did **what**, **where**, **when**, **from where**, and with what **result**", plus enough context to reconstruct important actions.

- For technical management purposes only (troubleshooting security, performance, ...)
- No sensitive data

### Implementation approach

- **Middleware-based:** A Starlette `BaseHTTPMiddleware` intercepts every request/response cycle
- **Async background writes:** Audit records are written via `asyncio.create_task()` so they never block the response
- **Append-only:** The `audit_log` table is insert-only; no updates or deletes
- **Error-resilient:** Audit write failures are logged but never break the request
- **Structured JSON to stdout:** Each audit record is also emitted as a single-line JSON object to stdout, providing three complementary access paths:
  1. **Database audit log** - quick queries and easy access with shorter, application-managed retention
  2. **Stdout** - real-time observability (e.g. `kubectl logs`, container log streams)
  3. **Stdout → external log management** - ship to ELK, Loki, Splunk etc. for longer retention than the application's configured retention period

### Audit fields

For each request that matters, capture:

| Field              | Source                      | Description                              | Answers |
| :----------------- | :-------------------------- | :--------------------------------------- | :------ |
| **timestamp**      | Server clock                | UTC, server default `now()`              | When    |
| **requestId**      | Generated                   | UUID4 correlation ID                     | -       |
| **roles**          | JWT `realm_access.roles`    | Comma-separated role list (nullable)     | Who     |
| **resourceType**   | Derived from path           | Entity type, e.g. `area`, `activity`     | Where   |
| **action**         | Derived from method + path  | Semantic action verb, e.g. `create`      | What    |
| **httpMethod**     | Request                     | HTTP method (`GET`, `POST`, `DELETE`)    | What    |
| **path**           | Request                     | Request path, e.g. `/api/ca/v1/areas`    | Where   |
| **httpStatusCode** | Response                    | HTTP status code                         | Result  |
| **statusCode**     | Derived from httpStatusCode | `OK` if httpStatusCode < 400, else `NOK` | Result  |
| **durationMs**     | Calculated                  | Request processing time in milliseconds  | -       |

### Action mapping

The middleware derives a semantic action and resource type from the HTTP method and request path:

| Method | Path pattern                  | Resource type | Action        |
| :----- | :---------------------------- | :------------ | :------------ |
| POST   | `/api/ca/v*/areas`            | `area`        | `create`      |
| GET    | `/api/ca/v*/areas`            | `area`        | `list`        |
| GET    | `/api/ca/v*/areas/count`      | `area`        | `count`       |
| GET    | `/api/ca/v*/areas/{id}`       | `area`        | `read`        |
| DELETE | `/api/ca/v*/areas/{id}`       | `area`        | `delete`      |
| POST   | `/api/str/v*/activities/bulk` | `activity`    | `create_bulk` |
| GET    | `/api/str/v*/areas`           | `area`        | `list`        |
| GET    | `/api/str/v*/areas/count`     | `area`        | `count`       |
| GET    | `/api/str/v*/areas/{id}`      | `area`        | `read`        |
| GET    | `/api/ca/v*/activities`       | `activity`    | `list`        |
| GET    | `/api/ca/v*/activities/count` | `activity`    | `count`       |
| POST   | `/api/auth/v*/token`          | `auth`        | `token`       |
| GET    | `/api/ping`                   | `system`      | `ping`        |

Unmatched paths fall back to action `unknown`.

### Example

```
| id  | timestamp                     | request_id   | roles                        | resource_type | action | http_method | path             | http_status_code | status_code | duration_ms |
| --- | ----------------------------- | ------------ | ---------------------------- | ------------- | ------ | ----------- | ---------------- | ---------------- | ----------- | ----------- |
| 20  | 2026-03-23 15:03:38.519686+00 | a34e8a0e-... | sdep_write,sdep_ca,sdep_read | system        | ping   | GET         | /api/ping        | 200              | OK          | 1           |
| 21  | 2026-03-23 15:03:39.864974+00 | 7bccb30b-... | sdep_write,sdep_ca,sdep_read | area          | create | POST        | /api/ca/v1/areas | 201              | OK          | 33          |
| 22  | 2026-03-23 15:03:39.947615+00 | f357d78c-... | sdep_write,sdep_ca,sdep_read | area          | create | POST        | /api/ca/v1/areas | 201              | OK          | 27          |
| 23  | 2026-03-23 15:03:40.02963+00  | 02294cf4-... | sdep_write,sdep_ca,sdep_read | area          | create | POST        | /api/ca/v1/areas | 201              | OK          | 18          |
```

### Skip list

The following paths are **not** audited (high-frequency, low-value):

- `/` (root)
- `/api/docs` (landing page)
- `/api/health`
- `/api/auth/v1/openapi.json`, `/api/ca/v1/openapi.json`, `/api/str/v1/openapi.json`
- `/api/auth/v1/docs`, `/api/ca/v1/docs`, `/api/str/v1/docs`

### Retention

Expired audit log rows are automatically deleted by a background task that runs every hour.

- The retention period is configurable via the `AUDITLOG_RETENTION` environment variable (default: **1 day**).
- Deletion is batched (1.000 rows per batch) to avoid long-running transactions.

The retention logic in `audit_retention.py` is split into two functions with distinct responsibilities:

- `delete_old_audit_logs` does the actual work;
- `audit_log_cleanup_loop` is the scheduler that ensures that work runs repeatedly for the lifetime of the application.

| Function                                                   | Responsibility                                                                                                                                                                                                                                                               | Invocation                                                                                                                                                                                                  |
| :--------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `delete_old_audit_logs(retention_days)`                    | **One-shot deletion.** Deletes all audit log rows older than `retention_days` in batches of 1.000. Returns the total number of deleted rows. This is a pure async function that runs to completion and then returns - it does not loop or sleep.                             | Called by `audit_log_cleanup_loop` on each cycle. Can also be called standalone in scripts, tests, or one-off maintenance tasks.                                                                            |
| `audit_log_cleanup_loop(retention_days, interval_seconds)` | **Infinite scheduling loop.** Calls `delete_old_audit_logs` once, then sleeps for `interval_seconds` (default 3.600 s = 1 hour), and repeats indefinitely until the task is cancelled. Catches and logs any exceptions so that a single failed cycle does not kill the loop. | Created as an `asyncio.Task` inside the FastAPI `lifespan` context manager in `main.py`. The task starts when the application boots and is cancelled (via `task.cancel()`) when the application shuts down. |
