<h1>Security</h1>

SDEP is an API-first application built to support machine-to-machine (M2M) interactions.

The following security considerations apply:

- [Identification](#identification)
- [Authentication and Authorization](#authentication-and-authorization)
- [Smaller Platforms](#smaller-platforms)
- [Audit Log](#audit-log)
- [OWASP](#owasp)
- [XSS, CSP, SQL, Path (Injection)](#xss-csp-sql-path-injection)
- [CSRF](#csrf)
- [Swagger UI](#swagger-ui)
- [File Upload](#file-upload)
- [Secrets](#secrets)
- [Security Headers](#security-headers)
- [Content-Disposition](#content-disposition)
- [Middleware Ordering](#middleware-ordering)
- [Security Headers, DNS, TLS](#security-headers-dns-tls)
- [Rate Limiting](#rate-limiting)
- [Dependency Version Pinning](#dependency-version-pinning)
- [Non-Root Containers](#non-root-containers)
- [Container Image Scans](#container-image-scans)
- [Authentication and Authorization (Details)](#authentication-and-authorization-details)
- [Audit Log (Details)](#audit-log-details)

*This document applies to the application scope only (CI/CD-aspects are outside the scope of this repo).*

## Identification

Upfront identification of machine-clients is handled process-wise (outside the scope of this repo).

## Authentication and Authorization

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

**Roles:**

| Role         | Purpose                    |
| :----------- | :------------------------- |
| `sdep_ca`    | Competent Authority access |
| `sdep_str`   | STR Platform access        |
| `sdep_read`  | Read operations            |
| `sdep_write` | Write operations           |

**JWT Claims used by the application:**

| Claim                | Maps to                                       |
| :------------------- | :-------------------------------------------- |
| `client_id`          | Platform or Competent Authority functional ID |
| `client_name`        | Platform or Competent Authority display name  |
| `realm_access.roles` | Role-based authorization                      |

## Smaller Platforms

Smaller platforms can opt for delegating SDEP API-invocation to third-parties.

In such case, the platform arranges data submission with their party; the party becomes registered in SDEP.

## Audit Log

The audit log, implemented in [`audit.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/security/audit.py), logs "**who** did **what**, **where**, **when**, **from where**, and with what **result**".

Scope:

- (Yet) for technical management only (troubleshooting security, performance, ...)
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

For more details, see section [Audit Log (Details)](#audit-log-details).

## OWASP

Measures taken based on:

- https://owasp.org/Top10/2025/
- https://owasp.org/API-Security/editions/2023/en/0x00-header/

| ID             | Subject                                         | Explanation                                                                               | Measure                                                                                        |
| :------------- | :---------------------------------------------- | :---------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| **A01:2025**   | Broken Access Control                           | Unauthorized access to data or functions                                                  | Endpoints secured by OAuth2 with JWT                                                           |
| **A02:2025**   | Security misconfiguration                       | Bad configurations / insecure defaults / environment mistakes                             | Externalized config (`config.py`)                                                              |
| **A03:2025**   | Software supply chain failures                  | Vulnerabilities in dependencies and external libraries                                    | [Container Image Scans](#container-image-scans) (part of CI/CD)                                |
| **A04:2025**   | Cryptographic failures                          | Failures in encryption, key management                                                    | TLS terminated at Gateway (part of CI/CD); RS256 for JWT in IAM (e.g. Keycloak, part of CI/CD) |
| **A05:2025**   | Injection                                       | Injection attacks (SQL, XSS, command, path, etc.)                                         | See section [XSS, CSP, SQL, Path (Injection)](#xss-csp-sql-path-injection) below               |
| **A06:2025**   | Insecure design                                 | Poor security considered already at design/architecture phase                             | Security by design (SDEP documentation)                                                        |
| **A07:2025**   | Authentication Failures                         | Weak or faulty authentication mechanisms (login, session management, credential handling) | Endpoints secured by OAuth2 with JWT                                                           |
| **A08:2025**   | Software or data integrity failures             | Failures in ensuring data / code integrity                                                | Pydantic validation (application) and source code control (part of CI/CD)                      |
| **A09:2025**   | Logging and alerting failures                   | Insufficient or missing logging/monitoring, alerting of security-relevant events          | Audit log                                                                                      |
| **A10:2025**   | Mishandling of exceptional conditions           | Improper handling of errors, exceptions, edge-cases, unexpected inputs or states          | Exception handling (`exception_handlers.py`)                                                   |
| **API1:2023**  | Broken Object Level Authorization               | Unauthorized access to objects by manipulating IDs                                        | Object-level scoping via JWT `client_id` in service/CRUD layer                                 |
| **API2:2023**  | Broken Authentication                           | Flawed identity verification allowing unauthorized access                                 | OAuth2 with JWT (RS256), JWKS key rotation, token proxy timeout                                |
| **API3:2023**  | Broken Object Property Level Authorization      | Exposing sensitive properties or allowing unauthorized property modification              | Pydantic schemas (explicit fields, no mass assignment, `frozen=True` on auth models)           |
| **API4:2023**  | Unrestricted Resource Consumption               | Missing limits on resources allowing DoS or cost exploitation                             | Upload/batch/pagination limits; rate limiting at deployment level                              |
| **API5:2023**  | Broken Function Level Authorization             | Accessing admin or restricted functions without proper authorization                      | Role-based endpoint protection via `RequireRoles`                                              |
| **API6:2023**  | Unrestricted Access to Sensitive Business Flows | Automated abuse of sensitive business operations at scale                                 | M2M only; client registration is process-controlled (not applicable)                           |
| **API7:2023**  | Server-Side Request Forgery                     | API fetches remote resources based on user-supplied URLs without validation               | No user-supplied URL fetching; IAM (e.g. Keycloak) URL is server-configured (not applicable)   |
| **API8:2023**  | Security Misconfiguration                       | Inappropriate security hardening across the application stack                             | Security headers, TLS, non-root container, no stack traces in responses                        |
| **API9:2023**  | Improper Inventory Management                   | Lack of visibility and documentation of API assets and versions                           | Versioned API mounts (`/api/{domain}/v1`); auto-generated OpenAPI docs                         |
| **API10:2023** | Unsafe Consumption of APIs                      | Integrating with external APIs without proper security controls                           | IAM (e.g. Keycloak) integration with TLS, timeout (10 s), JWKS caching                         |

## XSS, CSP, SQL, Path (Injection)

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

## File Upload

File upload is implemented in [`ca_areas.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/api/common/routers/ca_areas.py) (`post_area`).

File uploads are protected by:

- **Format:** only `.zip` files are accepted (validated by filename extension and ZIP magic bytes `PK\x03\x04`); non-zip uploads return `422`
- **Size:** max 1 MiB (`MAX_FILE_SIZE = 1_048_576`); oversized uploads return `422`

## Secrets

To avoid data leaks, secrets are externalized in [`config.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/config.py).

## Security Headers

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

Note: The `Access-Control-Allow-Origin` (CORS) header is not applicable for SDEP.

- SDEP is a backend API consumed by server-side clients using machine-to-machine (M2M) OAuth2 tokens
  - Server-to-server calls do not go through a browser
  - So CORS is never triggered
- Swagger UI is served from the same origin as the API
  - So its requests are same-origin and CORS does not apply

## Content-Disposition

Filenames in `Content-Disposition` response headers (area file downloads) are sanitized to prevent header injection:

- Characters that could break or inject headers are stripped (`"`, `\`, CR, LF, control characters)
- Path separators (`/`, `\`) are replaced with `_`.

## Middleware Ordering

Starlette processes middleware LIFO (last added = outermost = runs first). In `main.py`:
1. **SecurityHeadersMiddleware** (outermost) - added last, runs first
2. **AuditLogMiddleware** (inner) - added first, runs inside security headers

## Security Headers, DNS, TLS

Although CI/CD-related aspects are outside the scope of this repo, additional test results for SDEP-NL are as follows.

- SDEP-NL scores `100%` on [internet.nl](https://internet.nl/site/sdep.gov.nl)
- This validates that transport-level security is correctly applied (poor basic configuration would increase the attack surface)

## Rate Limiting

Rate limiting protects against brute-force attacks and abuse, particularly on the unauthenticated `/token` endpoint where an attacker could attempt credential stuffing at network speed.

Rate limiting is usally applied per unique client IP address, and handled in the deployment environment (e.g. by a (Kubernetes) Nginx Ingress controller, (HAProxy) load balancer, ...).

These deployment aspects are outside the scope of this repo.

## Dependency Version Pinning

Dependencies are declared with flexible lower bounds (`>=`) in `pyproject.toml` and locked to exact versions in `uv.lock`.

**Why `>=` instead of `==` in `pyproject.toml`**

- `pyproject.toml` declares the minimum acceptable version of each dependency (the *intent*)
- `uv.lock` records the exact resolved version of every package, including transitive dependencies (the *pin*)
- The Dockerfile installs with `uv sync --frozen`, which enforces the lock file exactly — no version can drift at build time
- Using `==` in `pyproject.toml` would duplicate what the lock file already does, while making legitimate upgrades harder and not covering transitive dependencies

**Docker base images**

- The Python base image is pinned to a minor version (`python:3.13-slim`) via `ARG PYTHON_IMAGE`
- The `uv` installer is pinned to a specific release (`ghcr.io/astral-sh/uv:0.5.4`)
- PostgreSQL and Keycloak versions are externalized via environment variables in `docker-compose.yml`

**Keeping dependencies up to date**

- Running `uv lock --upgrade` regenerates the lock file with the latest compatible versions
- The lock file should be committed and reviewed as part of the normal change process

## Non-Root Containers

The Docker container runs as a non-root user (`app`), following the principle of least privilege. This limits the impact of a container escape or application compromise.

## Container Image Scans

To minimize exposure to Common Vulnerabilities and Exposures (CVEs), container image scanning is assumed to be part of CI/CD (outside the scope of this repository):

- Continuously monitor and remediate Critical and High severity CVEs.
- Implement remediation according to a “comply (fix) or explain” policy.

---

**Each EU member state implementing an SDEP is responsible for monitoring and remediating CVEs within its own CI/CD.**

## Authentication and Authorization (Details)

SDEP interacts with IAM (e.g. Keycloak) in two distinct ways: **token issuance** (active HTTP call) and **token validation** (local signature verification using cached public keys).

---

**Token issuance (proxy to Keycloak)**

When an external client needs a JWT, it calls SDEP's `/api/auth/v1/token` endpoint. SDEP acts as a proxy: it takes the client's `client_id` + `client_secret` (from HTTP Basic Auth or form body), forwards them to Keycloak's token endpoint at `/realms/sdep/protocol/openid-connect/token`, and returns the resulting JWT. This is a synchronous request-response — every token request hits Keycloak directly.

See [`auth.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/api/common/routers/auth.py).

---

**Token validation (JWKS public key verification)**

On every subsequent API call, the client sends the JWT as a `Bearer` token. SDEP verifies the token signature locally — without calling Keycloak on every request — using the JSON Web Key Set (JWKS) protocol:

1. Keycloak signs JWTs with its private RSA key and publishes the corresponding public keys at the JWKS endpoint: `/realms/sdep/protocol/openid-connect/certs`
2. `PyJWKClient` fetches that key set and caches it in-memory
3. For each incoming request, `get_signing_key_from_jwt(token)` reads the JWT's `kid` (key ID) header, finds the matching public key from the cached set, and verifies the RS256 signature
4. The decoded payload is returned — no HTTP call to Keycloak needed

See [`security.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/api/common/security.py).

---

**JWKS key rotation (5-minute TTL)**

`PyJWKClient` is configured with `cache_jwk_set=True` and `lifespan=300` (5 minutes). This ensures that when Keycloak rotates or revokes signing keys, SDEP picks up the changes within at most 5 minutes — without requiring a restart. The alternative (`@lru_cache`) would cache keys indefinitely, meaning rotated or revoked keys would never be refreshed until the process was restarted.

| Concern        | How it's addressed                                                                                                      |
| :------------- | :---------------------------------------------------------------------------------------------------------------------- |
| Performance    | 99.9% of requests use cached keys — no network call to Keycloak                                                         |
| Key rotation   | New keys are picked up within 5 minutes                                                                                 |
| Key revocation | Revoked keys stop being trusted within 5 minutes                                                                        |
| Thread safety  | `_get_jwks_client()` uses double-checked locking to ensure exactly one `PyJWKClient` instance is created across threads |

---

**Request authentication flow**

```
Client request with Bearer token
  → OAuth2ClientCredentials extracts the token from the Authorization header
    → verify_bearer_token() calls validate_jwt_token()
      → _get_jwks_client() returns the singleton PyJWKClient
        → client.get_signing_key_from_jwt(token) matches the JWT kid to a cached public key
          → jwt.decode() verifies signature + expiry using that key
            → get_parsed_token() extracts realm_access.roles, client_id, client_name
              → RequireRoles checks roles against endpoint requirements
                → Endpoint handler executes
```

See [`auth_dependencies.py`](https://github.com/SEMICeu/sdep/blob/main/backend/app/api/common/auth_dependencies.py).

## Audit Log (Details)

**Audit fields**

For each request that matters, capture:

| Field              | Source                      | Description                                                                   | Answers |
| :----------------- | :-------------------------- | :---------------------------------------------------------------------------- | :------ |
| **timestamp**      | Server clock                | UTC, server default `now()`                                                   | When    |
| **requestId**      | Generated                   | UUID4 correlation ID                                                          | -       |
| **roles**          | JWT `realm_access.roles`    | Verified roles, `REJECTED`, `UNAUTHORIZED`, or `null` (not yet authenticated) | Who     |
| **resourceType**   | Derived from path           | Entity type, e.g. `area`, `activity`                                          | Where   |
| **action**         | Derived from method + path  | Semantic action verb, e.g. `create`                                           | What    |
| **httpMethod**     | Request                     | HTTP method (`GET`, `POST`, `DELETE`)                                         | What    |
| **path**           | Request                     | Request path, e.g. `/api/ca/v1/areas`                                         | Where   |
| **httpStatusCode** | Response                    | HTTP status code                                                              | Result  |
| **statusCode**     | Derived from httpStatusCode | `OK` if httpStatusCode < 400, else `NOK`                                      | Result  |
| **durationMs**     | Calculated                  | Request processing time in milliseconds                                       | -       |

---

**Role extraction — only from verified tokens**

The audit middleware extracts `roles` from the JWT **only when the request succeeded** (HTTP status < 400). A successful response means the route's auth dependency already verified the token signature and roles — so the logged roles are trustworthy. For rejected requests, the `roles` field indicates why, preventing forged tokens from polluting the audit trail.

| Scenario                               | What happens                       | `roles` in audit log      |
| :------------------------------------- | :--------------------------------- | :------------------------ |
| Valid JWT, authorized (2xx)            | Auth dependency verified the token | Verified roles from token |
| Forged, tampered, or expired JWT (401) | Auth dependency rejected the token | `REJECTED`                |
| Valid JWT, missing required role (403) | Token valid, but role check failed | `UNAUTHORIZED`            |
| No JWT (e.g. `/token` endpoint)        | Not yet authenticated              | `null`                    |

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
- `/favicon.ico` (browsers request this automatically; the application does not serve a favicon)
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

- `delete_old_audit_logs` does the actual work.
- `audit_log_cleanup_loop` is the scheduler that ensures that work runs repeatedly for the lifetime of the application.

| Function                                                   | Responsibility                                                                                                                                                                                                                                                               | Invocation                                                                                                                                                                                                  |
| :--------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `delete_old_audit_logs(retention_days)`                    | **One-shot deletion.** Deletes all audit log rows older than `retention_days` in batches of 1.000. Returns the total number of deleted rows. This is a pure async function that runs to completion and then returns - it does not loop or sleep.                             | Called by `audit_log_cleanup_loop` on each cycle. Can also be called standalone in scripts, tests, or one-off maintenance tasks.                                                                            |
| `audit_log_cleanup_loop(retention_days, interval_seconds)` | **Infinite scheduling loop.** Calls `delete_old_audit_logs` once, then sleeps for `interval_seconds` (default 3.600 s = 1 hour), and repeats indefinitely until the task is cancelled. Catches and logs any exceptions so that a single failed cycle does not kill the loop. | Created as an `asyncio.Task` inside the FastAPI `lifespan` context manager in `main.py`. The task starts when the application boots and is cancelled (via `task.cancel()`) when the application shuts down. |

---

**Retention of stdout**

**For stdout**, retention is assumed to be part of the deployment environment (out of scope of this repo).
