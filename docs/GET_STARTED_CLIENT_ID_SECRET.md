<h1>Client ID & secret authentication</h1>

This guide illustrates how to use **client ID & secret authentication** with SDEP.

- Practice in a local running SDEP environment (**Local**)
- Operate against SDEP in pre-production (**PRE**)

> SDEP-NL production (PRD) supports client-signed JWT only, see [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md).

<h2>Table of contents</h2>

- [Overview](#overview)
- [Step 1: Configure environment (as admin)](#step-1-configure-environment-as-admin)
  - [1a. Local](#1a-local)
  - [1b. PRE](#1b-pre)
- [Step 2: Request access (as admin)](#step-2-request-access-as-admin)
  - [2a. Local](#2a-local)
  - [2b. PRE](#2b-pre)
- [Step 3: Receive connection info (as admin)](#step-3-receive-connection-info-as-admin)
  - [3a. Local](#3a-local)
  - [3b. PRE](#3b-pre)
- [Step 4: Authenticate (as machine)](#step-4-authenticate-as-machine)
  - [4a. Local](#4a-local)
  - [4b. PRE](#4b-pre)
- [Step 5: Ping (as machine)](#step-5-ping-as-machine)
  - [5a. Local](#5a-local)
  - [5b. PRE](#5b-pre)
- [Step 6: Invoke the SDEP API (as machine)](#step-6-invoke-the-sdep-api-as-machine)
  - [6a. Local](#6a-local)
  - [6b. PRE](#6b-pre)
- [Step 7: Authenticate (as admin, in Swagger UI)](#step-7-authenticate-as-admin-in-swagger-ui)
  - [7a. Local](#7a-local)
  - [7b. PRE](#7b-pre)
- [Step 8: Invoke the SDEP API (as admin, in Swagger UI)](#step-8-invoke-the-sdep-api-as-admin-in-swagger-ui)
  - [8a. Local](#8a-local)
  - [8b. PRE](#8b-pre)
- [Step 9: Rotate secret (as admin)](#step-9-rotate-secret-as-admin)
  - [9a. Local](#9a-local)
  - [9b. PRE](#9b-pre)

## Overview

SDEP supports **OAuth 2.0** with the Client Credentials Grant.

The Client Credentials Grant supports **two client authentication methods**:

- **Client-signed JWT**: the client signs a JWT with its private key (and sends it to SDEP), after registering its public key once (at SDEP, `private_key_jwt`, RFC 7523)
- **Client ID & secret**: the client sends a shared secret (to SDEP, `client_secret_post` / `client_secret_basic`, RFC 6749)
- In SDEP, both authentication methods operate on the same `/token` endpoint.

This document focuses on **client ID & secret** (only local and PRE, not in PRD).

- See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for the other method.
- See [Authentication and authorization](./SECURITY.md#authentication-and-authorization) for general info.

---

Client ID & secret authentication is the easy option for testing.

- It requires no keypair.
- It allows you to paste your client ID & secret directly into the Swagger UI **Authorize** button.
- It is less secure than client-signed JWT, because the secret is shared with the authorization server.

In SDEP-NL PRE, the client ID & secret method is an **optional add-on** to the mandatory [client-signed JWT](./GET_STARTED_CLIENT_SIGNED_JWT.md) method.

- Each method gets its own client (account).
- The two accounts do not see each other's data.

The following actions are performed by the **client**, and are further explained in the sections below:

- As admin:
  - Request a client ID & secret from team SDEP
  - Receive **connection info** (incl. client ID & secret) from team SDEP
  - Keep the **secret** for yourself
- As machine (program):
  - **Authenticate** at the SDEP `/token` endpoint, using the client ID & secret
  - Receive a `Bearer` token from the `/token` endpoint
  - Invoke the functional (authenticated) SDEP API endpoints, using the received `Bearer` token in the HTTP `Authorization` header
  - **Re-authenticate** before the `Bearer` token expires (5 minutes), or on the first `401`

The following actions are performed by **team SDEP** (e.g. SDEP-NL), and are further explained in the sections below:

- Receive a request for SDEP access from the client
- Create a Keycloak machine client (with required roles) and its secret
- Hand out the connection info (incl. client ID & secret) to the client

## Step 1: Configure environment (as admin)

### 1a. Local

Start the local stack (postgres, keycloak, backend and test data), when not yet running:

```bash
make up
```

Client ID & secret authentication is enabled by default (`CLIENT_SECRET_AUTH_ENABLED=true` in `.env`).

If your `.env.extra` sets it to `false` (e.g. after following the client-signed JWT guide), remove that line or set it to **true**:

```bash
CLIENT_SECRET_AUTH_ENABLED=true
```

Recreate the backend for the change to take effect:

```bash
make backend-recreate
```

Result:

- Both client-signed JWT and client ID & secret authentication are enabled
- In Swagger UI, authorization is performed using a client ID & secret

---

### 1b. PRE

N/A.

## Step 2: Request access (as admin)

### 2a. Local

N/A - the test clients are predefined in `keycloak/machine-clients.yaml`, and provisioned by `make up` (idempotent):

```bash
make up
```

There is a client for each of the supported SDEP roles (CA, STR, AMA, STA, LSA, LMA), in two flavours:

- `sdep-test-*`: test data is removed after each automated test run
- `sdep-*` (without `test`): test data is kept

---

### 2b. PRE

In your email to team SDEP-NL, ask for the optional client ID & secret, see [Contact team SDEP-NL](./GET_STARTED_PRE.md#contact-team-sdep-nl).

## Step 3: Receive connection info (as admin)

Info comprises the client ID & secret, as well as other connection details.

---

### 3a. Local

Connection details are predefined.

Load `.env` into your shell:

```bash
set -a && source .env && set +a
```

Create exports based on `.env`:

```bash
export SDEP_BASE_URL="$BACKEND_BASE_URL"
```

```bash
export SDEP_TOKEN_URL="${SDEP_BASE_URL%/}/api/auth/v1/token"
```

Then create the exports for one of the test clients in `keycloak/machine-clients.yaml` (e.g. `sdep-str.01`):

```bash
export CLIENT_ID=sdep-str.01
```

```bash
export CLIENT_SECRET="$(yq -r ".clients[] | select(.id == \"$CLIENT_ID\") | .secret" keycloak/machine-clients.yaml)"
```

---

### 3b. PRE

You will receive the client ID & secret and connection details from team SDEP.

Create exports based on the values from team SDEP:

```bash
export SDEP_BASE_URL="as_received"; echo SDEP_BASE_URL $SDEP_BASE_URL
```

```bash
export SDEP_TOKEN_URL="as_received"; echo SDEP_TOKEN_URL $SDEP_TOKEN_URL
```

```bash
export CLIENT_ID="as_received"; echo CLIENT_ID $CLIENT_ID
```

```bash
export CLIENT_SECRET="as_received"
```

Explanation:

| Value            | Purpose                                   |
| ---------------- | ----------------------------------------- |
| `SDEP_BASE_URL`  | SDEP API base URL                         |
| `SDEP_TOKEN_URL` | SDEP API token endpoint (to authenticate) |
| `CLIENT_ID`      | Client identifier                         |
| `CLIENT_SECRET`  | Shared secret of the client **[1]**       |

[1] Treat it as a password: never share it, never commit it, and never print it in logs.

## Step 4: Authenticate (as machine)

### 4a. Local

Invoke the `/token` endpoint with the client ID & secret as form parameters:

```bash
export TOKEN_RESPONSE="$(
  curl -sS -X POST "$SDEP_TOKEN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=client_credentials" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_secret=$CLIENT_SECRET"
)"
```

Show the token response:

```bash
echo "$TOKEN_RESPONSE" | jq .
```

Extract the access token (Bearer) from the token response:

```bash
export ACCESS_TOKEN="$(echo "$TOKEN_RESPONSE" | jq -er '.access_token')" \
  || { echo "❌ No access token:"; echo "$TOKEN_RESPONSE" | jq .; }
```

Remarks:

- Instead of form parameters, you can also send the client ID & secret via HTTP Basic Authentication (`curl -u "$CLIENT_ID:$CLIENT_SECRET"`).
- The access token is used in the `Authorization` header when calling the API in the next step.
- The access token expires after **5 minutes**.
- Automate this step when your client needs long-running access.

---

### 4b. PRE

Same as [4a. Local](#4a-local).

## Step 5: Ping (as machine)

### 5a. Local

Verify the token with the role-agnostic ping endpoint:

```bash
curl -sS "$SDEP_BASE_URL/api/ping" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .
```

A valid token returns `{"status": "OK"}`.

Reuse the same `ACCESS_TOKEN` for as many calls as needed, until it expires after 5 minutes.

---

### 5b. PRE

Same as [5a. Local](#5a-local).

## Step 6: Invoke the SDEP API (as machine)

### 6a. Local

The API calls are the same for both authentication methods, only the way to get the `ACCESS_TOKEN` differs.

See the examples per role in [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md#8d-examples-ca), assume client environment is already set.

---

### 6b. PRE

Same as [6a. Local](#6a-local).

## Step 7: Authenticate (as admin, in Swagger UI)

### 7a. Local

Make sure your environment is prepared for client ID & secret (see [step 1a](#1a-local)).

In Swagger UI, select **Authorize** and enter your client ID & secret.

- Swagger UI acquires the `Bearer` token for you, at the `/token` endpoint
- There is no need to acquire a `Bearer` token programmatically first

---

### 7b. PRE

> Only when you requested client credentials for this authentication method.

In Swagger UI, select **Authorize** and enter your client ID & secret.

- Swagger UI acquires the `Bearer` token for you, at the `/token` endpoint
- There is no need to acquire a `Bearer` token programmatically first

## Step 8: Invoke the SDEP API (as admin, in Swagger UI)

### 8a. Local

Once authorized in Swagger UI (see [step 7a](#7a-local)), try out the other endpoints of your role:

- Open an endpoint, select **Try it out**, fill in the parameters, and select **Execute**
- Swagger UI shows the request as a `curl` command, plus the response
- Only the endpoints of your role are allowed, others return `403 Forbidden`

---

### 8b. PRE

> Only when you requested client credentials for this authentication method.

Same as [8a. Local](#8a-local).

## Step 9: Rotate secret (as admin)

### 9a. Local

N/A - the secrets are predefined in `keycloak/machine-clients.yaml`.

---

### 9b. PRE

Rotate a secret by coordinating the update with SDEP:

1. Ask SDEP for a new secret.
2. Wait for SDEP to hand out and confirm the new secret.
3. Start authenticating with the new secret.
4. Discard the old secret, it is no longer accepted.
