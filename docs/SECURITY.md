<h1>Security</h1>

SDEP is an API-first application built to support machine-to-machine (M2M) interactions.

The following security considerations apply:

- [Identification](#identification)
- [Authentication and authorization](#authentication-and-authorization)
- [Smaller platforms](#smaller-platforms)
- [Audit log](#audit-log)
- [OWASP](#owasp)
- [XSS, CSP, SQL, Path (injection)](#xss-csp-sql-path-injection)
- [CSRF](#csrf)
- [Swagger UI](#swagger-ui)
- [File upload](#file-upload)
- [Secrets](#secrets)
- [Dependency scanning](#dependency-scanning)
- [Security headers](#security-headers)
- [Security headers, DNS, TLS](#security-headers-dns-tls)
- [Audit log (details)](#audit-log-details)

*This document applies to the application scope only, as CI/CD-related aspects are outside the scope of this repo.*

## Identification

Upfront identification of machine-clients is handled process-wise (outside the scope of this repo).

## Authentication and authorization

For authentication and authorization, SDEP adopts OAuth 2.0 with JWT-based authentication, which is the industry standard for trusted machine-to-machine (M2M) communication using the OAuth 2.0 Client Credentials Flow (RFC 6749, section 4.4).

https://datatracker.ietf.org/doc/html/rfc6749#section-4.4

**Authentication** proves who the client is.

- For machine-to-machine (M2M) communication, the client uses the Client Credentials Flow to identify itself to the authorization server in exchange for an access token
- Authentication typically takes place via client_id and client_secret, or a signed JWT assertion

SDEP-NL adopts client_id and client_secret, motivated by:

- Compatibility: better support across legacy libraries and third-party tools.
- Reduced complexity: avoids the operational burden of managing keystores and certificates.

**Authorization** determines what the client is allowed to do.

- Based on the client's identity and pre-configured permissions, the server issues an access token containing specific scopes.
- The client then presents this as a Bearer token during API calls to access protected resources.

## Smaller platforms

Smaller platforms can opt for delegating SDEP API-invocation to third-parties.

In such case, the platform arranges data submission with their party; the party becomes registered in SDEP.

## Audit log

The audit log, implemented in [`audit.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/security/audit.py), logs "**who** did **what**, **where**, **when**, **from where**, and with what **result**".

Scope:

- For technical management only (troubleshooting security, performance, ...)
- Enough context to reconstruct important actions
- No sensitive (personal) data

Implementation approach as follows.

---

**Middleware-based audit capture**

A Starlette `BaseHTTPMiddleware` intercepts each request/response cycle and creates an audit record for every relevant interaction.

---

**Non-blocking audit writes**

Audit records are persisted asynchronously using `asyncio.create_task()`, so audit logging does not block or delay the application response path.

---

**Primary output: `audit_log` database table**

Audit records are written to the `audit_log` table in the application database.

- **Append-only:** records are inserted only; existing audit records are not updated or deleted.
- **Error-resilient:** audit write failures are logged, but they do not interrupt or fail the original request.
- **Application-managed retention:** database retention is handled by the application and may be shorter than external log retention.

---

**Secondary output: structured JSON to stdout**

Each audit record is also emitted as a single-line structured JSON object to stdout.

---

**Complementary access paths**

Together, the database table and stdout output provide complementary access paths:

- **Database audit log:** convenient for application-level querying, investigation, and short-to-medium-term retention.
- **Stdout:** useful for real-time operational visibility, for example when viewing container logs.
- **Stdout → external log management:** stdout can be collected by the runtime environment and forwarded to external log tooling, such as an Elastic/Kibana-based stack, for centralized search and longer retention.

---

**Deployment and log shipping are out of scope**

- This document defines how the application produces audit records and where it emits them.
- (Kubernetes) deployment details and external log management configuration are outside the scope of this repo.

---

For more details, see section [Audit log (details)](#audit-log-details).


## OWASP

Measures taken based on https://owasp.org/Top10/2025/:

| ID           | Subject                               | Explanation                                                                               | Measure                                                                                 |
| :----------- | :------------------------------------ | :---------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------- |
| **A01:2025** | Broken Access Control                 | Unauthorized access to data or functions                                                  | Endpoints secured by OAuth2 with JWT                                                    |
| **A02:2025** | Security misconfiguration             | Bad configurations / insecure defaults / environment mistakes                             | Externalized config (`config.py`)                                                       |
| **A03:2025** | Software supply chain failures        | Vulnerabilities in dependencies and external libraries                                    | Image scans (part of CI/CD)                                                             |
| **A04:2025** | Cryptographic failures                | Failures in encryption, key management                                                    | TLS terminated at Gateway (part of CI/CD); RS256 for JWT (e.g. Keycloak, part of CI/CD) |
| **A05:2025** | Injection                             | Injection attacks (SQL, XSS, command, path, etc.)                                         | See section XSS, CSP, SQL, Path (injection)  below                                      |
| **A06:2025** | Insecure design                       | Poor security considered already at design/architecture phase                             | Security by design (SDEP documentation)                                                 |
| **A07:2025** | Authentication Failures               | Weak or faulty authentication mechanisms (login, session management, credential handling) | Endpoints secured by OAuth2 with JWT                                                    |
| **A08:2025** | Software or data integrity failures   | Failures in ensuring data / code integrity                                                | Pydantic validation and source code control (part of CI/CD)                             |
| **A09:2025** | Logging and alerting failures         | Insufficient or missing logging/monitoring, alerting of security-relevant events          | Audit log                                                                               |
| **A10:2025** | Mishandling of exceptional conditions | Improper handling of errors, exceptions, edge-cases, unexpected inputs or states          | Exception handling (`exception_handlers.py`)                                            |

## XSS, CSP, SQL, Path (injection)

---

**XSS, CSP**

A **Cross-Site Scripting attack (XSS)** has three phases:

1. **Input** — the attacker injects malicious content (e.g. `<script>`)
2. **Storage / Reflection** — the application returns that content to a user
3. **Output / Execution** — the browser executes the script

SDEP mitigates these phases as follows.

**Input** is validated and rejected, to avoid injection.

- Server-side validation by FastAPI and Pydantic
- Rejects incorrect data types before the handler runs

**Output** is escaped, to avoid returning executable content:

- FastAPI automatically JSON-serializes all responses
- Special characters (`<`, `>`, `"`, `'`) are escaped in JSON output

**Route-specific Content Security Policy headers (CSP)** are added, to avoid foreign script execution in browser:

- Implemented in the [`headers.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/security/headers.py) middleware (tells the browser which sources are allowed to execute, and blocks everything else)
- Applies a **route-specific CSP** (strict on all API and root paths, relaxed only on Swagger UI docs pages)
- Motivation: Swagger UI requires `'unsafe-inline'` for its inline scripts and `style=""` attributes (nonces/hashes cannot cover the inline style attributes here)
- https://thecodebuzz.com/content-security-policy-csp-swagger-ui-openapi/

---

**SQL**

A **SQL injection** attack manipulates database queries by inserting malicious SQL fragments into user input (e.g. `' OR 1=1 --`), potentially reading, modifying, or deleting data.

SQL injection is mitigated by design through the technology stack:

- All database access uses **SQLAlchemy ORM** with its query builder API (`select()`, `insert()`, `update()`, `delete()`)
- All user-supplied values are passed as **bound parameters** — SQLAlchemy never interpolates values into SQL strings
- There are **no raw SQL strings** anywhere in the codebase (including audit log retention, which also uses the SQLAlchemy query builder)
- Pydantic validates and constrains all input **before** it reaches the database layer (type checks, max lengths, regex patterns)

---

**Path**

A **path traversal** attack manipulates file paths by inserting directory traversal sequences (e.g. `../../etc/passwd`) into user input, potentially reading or overwriting files outside the intended directory.

Path traversal is mitigated by design through the application architecture:

- **No filesystem operations on user-supplied input** — uploaded files are read into memory and stored as binary blobs (`LargeBinary`) in the database, not written to disk
- The uploaded filename is stored as metadata in the database only; it is **never used to construct filesystem paths**
- All functional IDs (used in URL path parameters and form fields) are validated against a strict alphanumeric pattern (`^[A-Za-z0-9\-]+$` in [`common.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/schemas/common.py)), which rejects path traversal characters (`/`, `\`, `.`, `..`)
- JWT claims used as identifiers (`client_id`) are validated against the same pattern before use

## CSRF

Cross-Site Request Forgery (CSRF) allows an attacker to trick a logged-in user into performing actions they didn't intend to do (via another website).

Cross-Site Request Forgery (CSRF) is not applicable for SDEP:

- SDEP uses stateless JWT bearer tokens in the `Authorization` header, not cookies — a browser cannot automatically attach credentials to a forged request, so CSRF is not possible
- Swagger UI authenticates via the same bearer token mechanism — no cookies are used, so CSRF-tokens and cookie attributes (`SameSite=Strict; Secure; HttpOnly`) do not apply

See also [`security.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/api/common/security.py) (`OAuth2ClientCredentials`).

## Swagger UI

The Swagger UI is intentionally served publicly by FastAPI without authentication, because the API itself is open source.

- As such, exposing the API documentation is considered an accepted and safe design decision rather than a security risk
- Potential risks related to public Swagger UI exposure and unauthorized access to API documentation are therefore not applicable in this context

Unauthorized usage of API endpoints is mitigated through the OAuth2 client-credentials flow using JWT bearer tokens.

## File upload

File upload is implemented in [`ca_areas.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/api/common/routers/ca_areas.py) (`post_area`).

File uploads are protected by size limit (`MAX_FILE_SIZE = 1_048_576` = 1 MiB)

- Oversized uploads return `422`.

Todo:

- Only accept .zip as input format - see comments in issue [#73](https://github.com/SEMICeu/sdep/issues/73)
- This change is beyond the current CA v1 freeze (because contract narrowing)

## Secrets

To avoid data leaks, secrets are externalized in [`config.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/config.py).

## Dependency scanning

To avoid common vulnerabilities (CVEs), image scans are assumed to be part of CI/CD (out of scope of this repo).

## Security headers

To avoid misuse on various layers, HTTP-headers are hardened in [`main.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/main.py) and [`headers.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/security/headers.py):

| Layer                           | HTTP-header                                                                                                                       | Avoids                                                                                                             |
| :------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Cache control (sensitive paths) | `Cache-Control: no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0` on `/api/auth/**`, `/api/ca/**`, `/api/str/**`  | Cached responses leaking authentication tokens or personal data                                                    |
| Content security                | `Content-Security-Policy: default-src 'self'; script-src 'self'; ...` (CSP)                                                       | Cross-site scripting (XSS), code injection, and data exfiltration                                                  |
| Cross-origin                    | `Cross-Origin-Embedder-Policy: require-corp` (COEP)                                                                               | Cross-origin resource leaks via embedded content (consider `unsafe-none` if encountering 504 issues in deployment) |
| Cross-origin                    | `Cross-Origin-Opener-Policy: same-origin` (COOP)                                                                                  | Browsing context from cross-origin openers                                                                         |
| Cross-origin                    | `Cross-Origin-Resource-Policy: same-origin` (CORP)                                                                                | Other origins loading SDEP responses                                                                               |
| Encryption                      | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` (HSTS)                                                  | Plain (unencrypted) HTTP-sniffing                                                                                  |
| Frame protection                | `frame-ancestors 'none'`                                                                                                          | Clickjacking                                                                                                       |
| Frame protection                | `X-Frame-Options: DENY`                                                                                                           | Clickjacking                                                                                                       |
| MIME protection                 | `X-Content-Type-Options: nosniff`                                                                                                 | MIME-sniffing                                                                                                      |
| Permissions                     | `Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), speaker=(self)` | Unauthorized access to device features (geolocation, microphone, ...)                                              |
| Referrer policy                 | `Referrer-Policy: no-referrer`                                                                                                    | Information leakage via Referer                                                                                    |

Although CI/CD-related aspects are outside the scope of this repo, test results for SDEP-NL are as follows.

- SDEP-NL scores `A+` on [securityheaders.com](https://securityheaders.com/?q=https%3A%2F%2Fsdep.gov.nl)
- This validates that response headers provide adequate browser-side protection

Note: the `Access-Control-Allow-Origin` (CORS) header is not applicable for SDEP.

- SDEP is a backend API consumed by server-side clients using machine-to-machine (M2M) OAuth2 tokens
  - Server-to-server calls do not go through a browser
  - So CORS is never triggered
- Swagger UI is served from the same origin as the API
  - So its requests are same-origin and CORS does not apply

## Security headers, DNS, TLS

Although CI/CD-related aspects are outside the scope of this repo, additional test results for SDEP-NL are as follows.

- SDEP-NL scores `100%` on [internet.nl](https://internet.nl/site/sdep.gov.nl)
- This validates that transport-level security is correctly applied (poor basic configuration would increase the attack surface)

## Audit log (details)

**Audit fields**

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

---

**Action mapping**

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

---

**Example**

```
| id  | timestamp                     | request_id   | roles                        | resource_type | action | http_method | path             | http_status_code | status_code | duration_ms |
| --- | ----------------------------- | ------------ | ---------------------------- | ------------- | ------ | ----------- | ---------------- | ---------------- | ----------- | ----------- |
| 20  | 2026-03-23 15:03:38.519686+00 | a34e8a0e-... | sdep_write,sdep_ca,sdep_read | system        | ping   | GET         | /api/ping        | 200              | OK          | 1           |
| 21  | 2026-03-23 15:03:39.864974+00 | 7bccb30b-... | sdep_write,sdep_ca,sdep_read | area          | create | POST        | /api/ca/v1/areas | 201              | OK          | 33          |
| 22  | 2026-03-23 15:03:39.947615+00 | f357d78c-... | sdep_write,sdep_ca,sdep_read | area          | create | POST        | /api/ca/v1/areas | 201              | OK          | 27          |
| 23  | 2026-03-23 15:03:40.02963+00  | 02294cf4-... | sdep_write,sdep_ca,sdep_read | area          | create | POST        | /api/ca/v1/areas | 201              | OK          | 18          |
```

---

**Skip list**

The following paths are **not** audited (high-frequency, low-value):

- `/` (root)
- `/api/docs` (landing page)
- `/api/health`
- `/api/auth/v1/openapi.json`, `/api/ca/v1/openapi.json`, `/api/str/v1/openapi.json`
- `/api/auth/v1/docs`, `/api/ca/v1/docs`, `/api/str/v1/docs`

---

**Retention of the database**

**For the database table**, expired audit log rows are automatically deleted by a background task that runs every hour.

- The retention period is configurable via the `AUDITLOG_RETENTION` environment variable (default: **1 day**).
- Deletion is batched (1.000 rows per batch) to avoid long-running transactions.

The retention logic in `audit_retention.py` is split into two functions with distinct responsibilities:

- `delete_old_audit_logs` does the actual work;
- `audit_log_cleanup_loop` is the scheduler that ensures that work runs repeatedly for the lifetime of the application.

| Function                                                   | Responsibility                                                                                                                                                                                                                                                               | Invocation                                                                                                                                                                                                  |
| :--------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `delete_old_audit_logs(retention_days)`                    | **One-shot deletion.** Deletes all audit log rows older than `retention_days` in batches of 1.000. Returns the total number of deleted rows. This is a pure async function that runs to completion and then returns - it does not loop or sleep.                             | Called by `audit_log_cleanup_loop` on each cycle. Can also be called standalone in scripts, tests, or one-off maintenance tasks.                                                                            |
| `audit_log_cleanup_loop(retention_days, interval_seconds)` | **Infinite scheduling loop.** Calls `delete_old_audit_logs` once, then sleeps for `interval_seconds` (default 3.600 s = 1 hour), and repeats indefinitely until the task is cancelled. Catches and logs any exceptions so that a single failed cycle does not kill the loop. | Created as an `asyncio.Task` inside the FastAPI `lifespan` context manager in `main.py`. The task starts when the application boots and is cancelled (via `task.cancel()`) when the application shuts down. |

---

**Retention of stdout**

**For stdout**, retention is assumed to be part of the deployment environment (out of scope of this repo).
