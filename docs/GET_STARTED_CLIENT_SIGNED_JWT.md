<h1>Client-Signed JWT Authentication</h1>

This guide illustrates how to use **client-signed JWT authentication** with SDEP.

- Practice in a local environment (**Local**)
- Deploy against SDEP pre-production (**PRE**) and production (**PRD**)

<h2>Table of Contents</h2>

- [Overview](#overview)
- [Step 1: Configure Environment (as admin)](#step-1-configure-environment-as-admin)
  - [1a. Local](#1a-local)
  - [1b. PRE](#1b-pre)
  - [1c. PRD](#1c-prd)
- [Step 2: Configure Keypair (as admin)](#step-2-configure-keypair-as-admin)
  - [2a. Local](#2a-local)
  - [2b. PRE](#2b-pre)
  - [2c. PRD](#2c-prd)
- [Step 3: Send Keypair (as admin)](#step-3-send-keypair-as-admin)
  - [3a. Local](#3a-local)
  - [3b. PRE](#3b-pre)
  - [3c. PRD](#3c-prd)
- [Step 4: Receive Connection Info (as admin)](#step-4-receive-connection-info-as-admin)
  - [4a. Local](#4a-local)
  - [4b. PRE](#4b-pre)
  - [4c. PRD](#4c-prd)
- [Step 5: Create a Client-Signed JWT (as machine)](#step-5-create-a-client-signed-jwt-as-machine)
  - [5a. Local](#5a-local)
  - [5b. PRE](#5b-pre)
  - [5c. PRD](#5c-prd)
- [Step 6: Authenticate (as machine)](#step-6-authenticate-as-machine)
  - [6a. Local](#6a-local)
  - [6b. PRE](#6b-pre)
  - [6c. PRD](#6c-prd)
- [Step 7: Ping (as machine)](#step-7-ping-as-machine)
  - [7a. Local](#7a-local)
  - [7b. PRE](#7b-pre)
  - [7c. PRD](#7c-prd)
- [Step 8: Invoke the SDEP API (as machine)](#step-8-invoke-the-sdep-api-as-machine)
  - [8a. Local](#8a-local)
  - [8b. PRE](#8b-pre)
  - [8c. PRD](#8c-prd)
  - [8d. Examples (CA)](#8d-examples-ca)
  - [8e. Examples (STR)](#8e-examples-str)
  - [8f. Examples (REP)](#8f-examples-rep)
- [Step 9: Authenticate (as admin, in Swagger)](#step-9-authenticate-as-admin-in-swagger)
  - [9a. Local](#9a-local)
  - [9b. PRE](#9b-pre)
  - [9c. PRD](#9c-prd)
- [Step 10: Rotate Keys (admin)](#step-10-rotate-keys-admin)
  - [10a. Local](#10a-local)
  - [10b. PRE](#10b-pre)
  - [10c. PRD](#10c-prd)

## Overview

SDEP supports **OAuth 2.0** with the **Client Credentials Grant**.

The Client Credentials Grant itself supports **two client authentication methods**:

- **Client ID & secret**: the client sends a shared secret (to SDEP)
- **Client-signed JWT**: the client signs a JWT with its private key (and send it to SDEP), after registering its public key once (at SDEP, `private_key_jwt`, RFC 7523)

For SDEP, both authentication methods operate on the same `/token` endpoint.

- See [Authentication and Authorization](./SECURITY.md#authentication-and-authorization) for more info on both authentication methods.
- This document focuses on **client-signed JWT**.

---

Client-signed JWT authentication uses a private/public key pair to get authenticated.

The following actions are performed by the **client**, and are further explained in the sections below:

- As admin:
  - Create a **private/public key pair**
  - Keep the **private key** for yourself
  - Submit the **public key** to team SDEP
  - Receive **connection info** (such as the public key ID) from team SDEP
- As machine (program):
  - Create a **signed JWT** from the private key and the connection info
  - **Authenticate** at the SDEP `/token` endpoint, using the signed JWT
  - Receive a `Bearer` token from the `/token` endpoint
  - Invoke the functional (authenticated) SDEP API endpoints, using the received `Bearer` token in the HTTP `Authorization` header
  - **Re-authenticate** before the `Bearer` token expires (5 minutes), or on the first `401`
- Rotate the private/public key pair according to own security guidelines

The following actions are performed by **team SDEP** (e.g. SDEP-NL), and are further explained in the sections below:

- Receive a request for SDEP access from the client (incl. public key)
- Create a Keycloak machine client (with required roles), containing the public key (identified by public key ID = `kid`)
- Hand out the connection info (incl. `kid`) back to the client

## Step 1: Configure Environment (as admin)

### 1a. Local

In your `.env.extra`, set client-secret authentication to **false**:

```bash
CLIENT_SECRET_AUTH_ENABLED=false
```

Restart the backend for the change to take effect:

```bash
make backend-restart
```

Result:

- Only client-signed JWT authentication remains enabled
- In Swagger UI, authorization is performed exclusively using a Bearer token
- See [step 9](#9a-local) for follow-up

---

### 1b. PRE

N/A.

---

### 1c. PRD

N/A.

## Step 2: Configure Keypair (as admin)

### 2a. Local

In your local development environment, configuring a keypair is automated by any of these `make` commands:

```bash
make up # Idempotent
  └── make keycloak-configure
        └── keycloak-generate-machine-clients
```

These commands use `scripts/generate-keycloak-machine-clients.py`, which configures a **client-signed JWT test client** for each of the supported SDEP roles:

```
┌───────────────────┬─────────────────────────────────┐
│     Client id     │              Roles              │
├───────────────────┼─────────────────────────────────┤
│ sdep-test-ca.jwt  │ sdep_ca, sdep_read, sdep_write  │
├───────────────────┼─────────────────────────────────┤
│ sdep-test-str.jwt │ sdep_str, sdep_read, sdep_write │
├───────────────────┼─────────────────────────────────┤
│ sdep-test-rep.jwt │ sdep_rep, sdep_read             │
└───────────────────┴─────────────────────────────────┘
```

Generated configuration is as follows:

---

**Private keys**

Config:

- `./tmp/sdep-test-str.jwt.private.pem`
- `./tmp/sdep-test-rep.jwt.private.pem`
- `./tmp/sdep-test-ca.jwt.private.pem`

These will be used to authenticate at the local SDEP `/token` endpoint.

---

**Public keys**

Config:

- `./tmp/sdep-test-ca.jwt.public.yaml`
- `./tmp/sdep-test-rep.jwt.public.yaml`
- `./tmp/sdep-test-str.jwt.public.yaml`

These are used to extend the default `keycloak/machine-clients.yaml`:

---

**Machine clients**

Config:

- `tmp/machine-clients-extended.yaml`

This is the extended `keycloak/machine-clients.yaml`, and is fed into Keycloak.

---

**Smoke test**

For each test client, verify that the public key stored in Keycloak matches the private key in your own possession.

```bash
make keycloak-match-client-public-keys
```

Or show the public key for a single client instead:

```bash
make keycloak-show-client-public-key CLIENT_ID=sdep-test-str.jwt # sdep-test-ca.jwt, sdep-test-rep.jwt
```

---

### 2b. PRE

As admin, on the client system, generate a keypair:

```bash
openssl genpkey \
  -algorithm RSA \
  -pkeyopt rsa_keygen_bits:2048 \
  -out  your.private.pem

chmod 600  your.private.pem

openssl pkey \
  -in  your.private.pem \
  -pubout \
  -out  your.public.pem
```

This creates:

- ` your.private.pem`: a private key that will be used by your client to authenticate (by signing token requests at the `/token` endpoint)
- ` your.public.pem`: a public key that you will send to SDEP, to onboard your client in keycloak

Smoke test (pair):

```
diff <(openssl pkey -in your.private.pem -pubout) your.public.pem \
  && echo "✅ pair matches" || echo "❌ pair does NOT match"
```

> Always keep the private key exclusively in your possession.

---

### 2c. PRD

Same as PRE.

## Step 3: Send Keypair (as admin)

### 3a. Local

N/A.

---

### 3b. PRE

Send the complete content the ` your.public.pem` you created in [step 2b.](#2b-pre) to team SDEP, including the PEM markers:

```text
-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----
```

> Always keep the private key exclusively in your possession.

---

### 3c. PRD

Same as PRE.

## Step 4: Receive Connection Info (as admin)

Info comprises the public key ID to use (`kid`), as well as other connection details.

---

### 4a. Local

Public key ID and connection details are predefined.

Create exports based on `.env`:

```bash
set -a && source .env && set +a

export SDEP_BASE_URL="$BACKEND_BASE_URL"
export SDEP_TOKEN_URL="${SDEP_BASE_URL%/}/api/auth/v1/token"
export CLIENT_SIGNED_JWT_AUDIENCE="${BACKEND_KC_BASE_URL%/}/realms/sdep/protocol/openid-connect/token"
```

And create exports based on either client-signed JWT test client as confiured in [step 2a.](#2a-local):

```bash
export CLIENT_ID=sdep-test-str.jwt # sdep-test-ca.jwt, sdep-test-rep.jwt
export KEY_FILE="tmp/$CLIENT_ID.private.pem"
export KID="$CLIENT_ID"
```

---

### 4b. PRE

You will receive public key-id and connection details from team SDEP.

Based on this, equip your client environment.

For example as follows.

---

**Private key**

Create an export based on the private key file that you created in [step 2b](#2b-pre):

```bash
export KEY_FILE=" your.private.pem";  echo KEY_FILE $KEY_FILE
```

---

**Public key and connection**

Create exports based on the values from team SDEP:

```bash
export SDEP_BASE_URL="as_received";               echo SDEP_BASE_URL $SDEP_BASE_URL
export SDEP_TOKEN_URL"as_received";               echo SDEP_TOKEN_URL $SDEP_TOKEN_URL
export CLIENT_ID="as_received";                   echo CLIENT_ID $CLIENT_ID
export KID="as_received";                         echo KID $KID
export CLIENT_SIGNED_JWT_AUDIENCE="as_received";  echo CLIENT_SIGNED_JWT_AUDIENCE $CLIENT_SIGNED_JWT_AUDIENCE
```

Explanation:

| Value                        | Purpose                                         | Wiill appear in JWT as |
| ---------------------------- | ----------------------------------------------- | ---------------------- |
| `SDEP_BASE_URL`              | SDEP API base URL                               |                        |
| `SDEP_TOKEN_URL`             | SDEP API token endpoint (to authenticate)       |                        |
| `CLIENT_ID`                  | Client-signed JWT payload: issuer and subject   | `iss`, `sub`           |
| `KID`                        | Client-signed JWT header: public key identifier | `kid`                  |
| `CLIENT_SIGNED_JWT_AUDIENCE` | Client-signed JWT payload: audience **[1]**     | `aud`                  |

[1] This identifies the intended recipient of the JWT (the authorization server, e.g. Keycloak)

---

### 4c. PRD

Same as PRE.

## Step 5: Create a Client-Signed JWT (as machine)

To prepare for authentication.

---

### 5a. Local

For one-time usage (defined by the authorization server, repeat for each new authentication in [step 6a](#6a-local)) and only valid for 60 seconds (defined by the invoked `create-client-signed-jwt.py`).

Programmatically, by example:

```bash
export CLIENT_SIGNED_JWT="$(
  uv run scripts/create-client-signed-jwt.py \
    --token-url "$CLIENT_SIGNED_JWT_AUDIENCE" \
    --client-id "$CLIENT_ID" \
    --key-file "$KEY_FILE" \
    --kid "$KID"
)"

echo $CLIENT_SIGNED_JWT
```

> This example uses Python; you can also implement this in your own stack.

Details:

- SDEP maps `client_signed_jwt` to the authorization server's standard OAuth `private_key_jwt` request fields
- The script sets the required claims (`iss`, `sub`, `aud`, `iat`, `exp`, `jti`) and the `RS256`/`kid` header

---

### 5b. PRE

Same as Local.

---

### 5c. PRD

Same as Local.

## Step 6: Authenticate (as machine)

### 6a. Local

Use the client-signed JWT within 60 seconds, and only once, to invoke the `/token` endpoint:

```bash
# Get token response
export TOKEN_RESPONSE="$(
  curl -sS -X POST "$SDEP_TOKEN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=client_credentials" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_signed_jwt=$CLIENT_SIGNED_JWT"
)"

printf 'TOKEN_RESPONSE:\n\n'
echo "$TOKEN_RESPONSE" | jq .

# Extract access token (Bearer) from token response
export ACCESS_TOKEN="$(echo "$TOKEN_RESPONSE" | jq -er '.access_token')" \
  || { echo "❌ No access token:"; echo "$TOKEN_RESPONSE" | jq .; }
```

Remarks:

- The access token is used in the `Authorization` header when calling the API in the next step.
- The access token expires after **5 minutes**.
- Automate this step when your client needs long-running access.

---

### 6b. PRE

Same as Local.

---

### 6c. PRD

Same as Local.

## Step 7: Ping (as machine)

### 7a. Local

Verify the token with the role-agnostic ping endpoint:

```bash
curl -sS "$SDEP_BASE_URL/api/ping" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .
```

A valid token returns `{"status": "OK"}`.

Reuse the same `ACCESS_TOKEN` for as many calls as needed, until it expires after 5 minutes.

---

### 7b. PRE

Same as Local.

---

### 7c. PRD

Same as Local.

## Step 8: Invoke the SDEP API (as machine)

### 8a. Local

See examples below, assume client environment is already set.

---

### 8b. PRE

Same as Local.

---

### 8c. PRD

Same as Local.

---

### 8d. Examples (CA)

*Only when having the Competent Authority role (CA).*

```bash
# Count the own areas
curl -sS "$SDEP_BASE_URL/api/ca/v1/areas/count" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .

# Get the own areas (first 2)
curl -sS "$SDEP_BASE_URL/api/ca/v1/areas?limit=2" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .

# Get the activities in the own areas (first 2)
curl -sS "$SDEP_BASE_URL/api/ca/v1/activities?limit=2" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .
```

Example response:

```json
{
  "areas": [
    {
      "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
      "areaName": "Amsterdam",
      "regulation": "all",
      "filename": "Amsterdam.zip",
      "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
      "competentAuthorityName": "Amsterdam (inclusief Weesp)",
      "createdAt": "2025-01-01T00:00:00Z"
    }
    ...
  ]
}
```

Remarks:

- Results are scoped to the authenticated competent authority, based on the `client_id` in the access token
- See `docs/API.md` for the full endpoint list, including area upload and delete

---

**CA v2 (Beta): Activity Filters**

`/api/ca/v2` serves the same area endpoints as v1, unchanged. Only the activity endpoints differ: they add four optional filters.

```bash
# Count the own activities created in June 2025
curl -sS -G "$SDEP_BASE_URL/api/ca/v2/activities/count" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-urlencode "createdAtFrom=2025-06-01T00:00:00Z" \
  --data-urlencode "createdAtTo=2025-06-30T23:59:59Z" \
  | jq .

# Get the own activities for one area and one platform (first 2)
curl -sS -G "$SDEP_BASE_URL/api/ca/v2/activities" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-urlencode "areaId=58ff0814-3aa1-5019-9afb-3cd9f398602c" \
  --data-urlencode "platformId=8e70f1e2-4c61-477b-89b8-0dbf25ab8b21" \
  --data-urlencode "limit=2" \
  | jq .
```

Example response (count):

```json
{
  "count": 42
}
```

Remarks:

- Filters combine with AND, omitting a filter means no constraint on that dimension
- `createdAtFrom` and `createdAtTo` are inclusive and must be UTC (`Z` or `+00:00`); a naive datetime or another offset returns HTTP 400
- `platformId` and `areaId` are exact-match functional IDs, an invalid format returns HTTP 400
- Use `curl -G --data-urlencode` so the `:` in the timestamps is encoded for you
- For OR semantics, call the endpoint per value and combine the results client-side

---

### 8e. Examples (STR)

*Only when having the platform role (STR).*

```bash
# Count the areas
curl -sS "$SDEP_BASE_URL/api/str/v1/areas/count" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .

# Get the areas (first 2)
curl -sS "$SDEP_BASE_URL/api/str/v1/areas?limit=2" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .
```

Example response:

```json
{
  "areas": [
    {
      "areaId": "86de11c8-1744-5241-9c82-a19444d7a6d8",
      "areaName": "Zwolle",
      "regulation": "all",
      "filename": "Zwolle.zip",
      "competentAuthorityId": "10f2b986-802c-537f-82d2-8069a25c6c11",
      "competentAuthorityName": "Zwolle",
      "createdAt": "2025-01-01T00:00:00Z"
    }
    ...
  ]
}
```

---

### 8f. Examples (REP)

*Only when having "reporting and statistics offices" role (REP).*

```bash
# Count all activities
curl -sS "$SDEP_BASE_URL/api/rep/v1/activities/count" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .

# Get all activities (first 2)
curl -sS "$SDEP_BASE_URL/api/rep/v1/activities?limit=2" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .
```

Example response:

```json
{
  "activities": [
    {
      "activityId": "550e8400-e29b-41d4-a716-446655440000",
      "activityName": "Amsterdam Summer Rental",
      "status": "finished",
      "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
      "areaName": "Amsterdam",
      "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
      "competentAuthorityName": "Gemeente Amsterdam",
      "url": "http://example.com/amsterdam-myhouse-1",
      "address": {
        "thoroughfare": "Prinsengracht",
        "locatorDesignatorNumber": 263,
        "postCode": "1016GV",
        "postName": "Amsterdam",
        "fullAddress": "Prinsengracht 263, 1016GV Amsterdam"
      },
      "registrationNumber": "REG0001",
      "numberOfGuests": 4,
      "countryOfGuests": ["NLD", "DEU", "BEL", "N/A"],
      "temporal": {
        "startDatetime": "2025-06-01T14:00:00Z",
        "endDatetime": "2025-06-07T11:00:00Z"
      },
      "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
      "platformName": "Test STR 01 (interactive usage, persistent)",
      "createdAt": "2025-06-01T12:00:00Z"
    }
    ...
  ]
}
```

Remarks:

- Results are not scoped: they cover all competent authorities and all platforms
- `limit` defaults to 1000, which is also the maximum - page with `offset` and `/activities/count`
- Optional filters (AND semantics): `createdAtFrom`, `createdAtTo`, `platformId`, `areaId`, `competentAuthorityId`

## Step 9: Authenticate (as admin, in Swagger)

### 9a. Local

Make sure your environment is prepared for client-signed JWT (see [step 1](#1a-local)).

In Swagger UI, select **Authorize** and paste the Bearer token you programmatically obtained in [step 5](#step-5-create-a-client-signed-jwt-as-machine).

---

### 9b. PRE

N/A - in PRE, Swagger authorization is always performed using client ID & secret.

---

### 9c. PRD

In Swagger UI, select **Authorize** and paste the Bearer token you programmatically obtained in [step 5](#step-5-create-a-client-signed-jwt-as-machine).

## Step 10: Rotate Keys (admin)

### 10a. Local

Delete the generated private key and rerun local setup:

```bash
rm tmp/*.private.pem
make keycloak-generate-machine-clients
make keycloak-configure
```

---

### 10b. PRE

Rotate a key by coordinating the public-key update with SDEP:

1. Generate a new private/public key pair.
2. Send the new public key to SDEP.
3. Wait for SDEP to assign and confirm the new `kid`.
4. Start signing new client-signed JWTs with the new private key and `kid`.
5. Keep the old private key only until SDEP confirms it is no longer accepted.

---

### 10c. PRD

Same as PRE.
