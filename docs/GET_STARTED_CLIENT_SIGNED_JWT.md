<h1>Client-Signed JWT Authentication</h1>

This guide illustrates how to use **client-signed JWT authentication** with SDEP:

- Practice in a local environment
- Deploy against SDEP pre-production (PRE) and production (PRD)

<h2>Table of Contents</h2>

- [Introduction](#introduction)
- [Step 1. Configure Keypair (admin)](#step-1-configure-keypair-admin)
  - [1a. Local](#1a-local)
  - [1b. PRE, PRD](#1b-pre-prd)
- [Step 2. Configure Environment (admin)](#step-2-configure-environment-admin)
  - [2a. Local](#2a-local)
  - [2b. PRE, PRD](#2b-pre-prd)
- [Step 3: Create a Client-Signed JWT (machine)](#step-3-create-a-client-signed-jwt-machine)
- [Step 4: Authenticate (machine)](#step-4-authenticate-machine)
- [Step 5: Ping (machine)](#step-5-ping-machine)
- [Step 6: SDEP (machine)](#step-6-sdep-machine)
- [Step 7: Rotate Keys (admin)](#step-7-rotate-keys-admin)
  - [7a. Local](#7a-local)
  - [7b. PRE, PRD](#7b-pre-prd)

## Introduction

SDEP supports **OAuth 2.0** with the **Client Credentials grant**.

The Client Credentials grant supports **two authentication types**:

- **Client ID & secret**
- **Client-signed JWT**

Both authentication types operate on the same `/token` endpoint.

---

This document focuses on **client-signed JWT**.

- See [Authentication and Authorization](./SECURITY.md#authentication-and-authorization) for more info on both authentication types

---

Client-signed JWT authentication uses a private/public key pair to get authenticated.

Actions to be performed by **client** (admin/machine), furher explained in the following sections:

- Create a **private/public key pair**
- Keep the **private key** for yourself
- Submit the **public key** to team SDEP
- Receive **token request values** from team SDEP
- Program:
  - Create a **signed JWT** from private key and token request values
  - **Authenticate** at the SDEP `token/` endpoint, using the signed JWT
  - Receive a `Bearer` token from the `token/` endpoint
  - Invoke the functional (authenticated) SDEP API endpoints, using the `Bearer` token in the HTTP `Authorization` header
  - **Re-authenticate** on first failure or within 5 minutes (when `Bearer` tokens expire)
- Rotate private/public key pair conform own security guidelines

Actions to be performed by **team SDEP** (implemented for SDEP-NL), furher explained in the following sections:

- Receive request for SDEP access from client (incl. public key)
- Create a Keycloak machine client (with required roles) containing the public key (identified by `kid` = key-id)
- Hand-out token request values (incl. `kid`) back to client

Actions as follows:

## Step 1. Configure Keypair (admin)

---

### 1a. Local

Configuring a keypair is automated by choosing either `make` command:

```
make up                                 # Also invokes keycloak-up; or

make keycloak-up                        # Also invokes keycloak-generate-machine-clients + keycloak-configure; or

make keycloak-generate-machine-clients  # Idempotent

make keycloak-configure                 # Idempotent
```

---

**Result**: **client-signed JWT test clients** are configured, representing each of the supported SDEP roles:

- `sdep-test-ca.jwt` (representing CA)
- `sdep-test-str.jwt` (representing STR)
- `sdep-test-rep.jwt` (representing REP)

---

Explore the generated artifacts on disk:

- A generated **private key**, for each of the test clients (`tmp/*.private.pem`)
- A generated **public key**, for each of the test clients (`tmp/*.public.yaml`)
- A generated `tmp/machine-clients-extended.yaml`

The `tmp/machine-clients-extended.yaml` contains:

- A **client signed JWT test account**, for each `tmp/*.public.yaml`
- Client-secret test accounts, originating from `keycloak/machine-clients.yaml`
- The client-secret clients are further out of scope of this document.

---

For each test client, verify that the public key stored in Keycloak matches the private key in your own possession.

```bash
make keycloak-match-client-public-keys
```

Or show the public key for a single client instead:

```bash
make keycloak-show-client-public-key CLIENT_ID=sdep-test-str.jwt # sdep-test-ca.jwt, sdep-test-rep.jwt
```

---

### 1b. PRE, PRD

As admin, on the client system, generate a keypair:

```bash
openssl genpkey \
  -algorithm RSA \
  -pkeyopt rsa_keygen_bits:2048 \
  -out sdep-client.private.pem

chmod 600 sdep-client.private.pem

openssl pkey \
  -in sdep-client.private.pem \
  -pubout \
  -out sdep-client.public.pem
```

This creates:

- `sdep-client.private.pem`: private key used by your client to sign token requests (client-signed JWT)
- `sdep-client.public.pem`: public key sent to SDEP for onboarding

---

Send the complete content of `sdep-client.public.pem` to team SDEP, including the PEM markers:

```text
-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----
```

> Always keep the private key exclusively in your possession.

---

Receive **token request values** from team SDEP:

| Token request value        | Use As                       | Purpose                                                                                                                |
| -------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| SDEP base URL              | `SDEP_BASE_URL`              | SDEP API base URL                                                                                                      |
| SDEP token endpoint        | `SDEP_TOKEN_URL`             | SDEP API token endpoint (`/token`)                                                                                     |
| Client ID                  | `CLIENT_ID`                  | Client-signed JWT payload: issuer (`iss`) and subject (`sub`)                                                          |
| Key ID                     | `KID`                        | Client-signed JWT header: public key identifier (`kid`)                                                                |
| Client-signed JWT audience | `CLIENT_SIGNED_JWT_AUDIENCE` | Client-signed JWT payload: audience (`aud`) = authorization server token endpoint (Keycloak, part of token validation) |

## Step 2. Configure Environment (admin)

---

### 2a. Local

In your `.env.extra`, set client-secret authentication to **false**:

```bash
CLIENT_SECRET_AUTH_ENABLED=false
```

Restart the backend, to effectuate the setting:

```
make backend-restart
```

Result: client-signed JWT stays exclusively enabled and becomes visible in the **Swagger UI** Authorize.

---

To prepare for authentication by the client, create exports based on predefined values in `.env`:

```bash
set -a && source .env && set +a

export SDEP_BASE_URL="$BACKEND_BASE_URL"
export SDEP_TOKEN_URL="${SDEP_BASE_URL%/}/api/auth/v1/token"
export CLIENT_SIGNED_JWT_AUDIENCE="${BACKEND_KC_BASE_URL%/}/realms/sdep/protocol/openid-connect/token"
```

---

And create exports based on client-signed JWT test clients in `tmp/machine-clients-extended.yaml`:

```bash
export CLIENT_ID=sdep-test-str.jwt # sdep-test-ca.jwt, sdep-test-rep.jwt
export KEY_FILE="tmp/$CLIENT_ID.private.pem"
export KID="$CLIENT_ID"
```

---

### 2b. PRE, PRD

Create exports based on the received values from team SDEP (see above):

```bash
export SDEP_BASE_URL="..."
export SDEP_TOKEN_URL="..."
export CLIENT_SIGNED_JWT_AUDIENCE="..."
export CLIENT_ID="..."
export KID="..."
```

---

And create exports based on the private key file you created earlier:

```bash
export KEY_FILE="sdep-client.private.pem"
```

## Step 3: Create a Client-Signed JWT (machine)

Prepare for invoking the `token/` endpoint:

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

> This example uses Python; clients can also implement this in their own stack.

Remarks:

- A client-signed JWT can only be **used once**. A replayed JWT is rejected by the authorization server (Keycloak).
- The client-signed JWT created here is **valid for 60 seconds** (client-defined `exp`). Keep this lifetime short when signing in your own stack: the JWT only needs to survive one request.

Details:

- SDEP maps `client_signed_jwt` to the authorization server's standard OAuth `private_key_jwt` request fields
- The script sets the required claims (`iss`, `sub`, `aud`, `iat`, `exp`, `jti`) and the `RS256`/`kid` header

## Step 4: Authenticate (machine)

Use the client-signed JWT within 60 seconds, and only once, to invoke the `token/` endpoint:

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

- Access token will be used in the `Authorization` header when calling the API in the next step.
- Access token expires after **5 minutes**.
- Automate this step when your client needs long-running access.

## Step 5: Ping (machine)

Verify the token with the role-agnostic ping endpoint:

```bash
curl -sS "$SDEP_BASE_URL/api/ping" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq .
```

A valid token returns `{"status": "OK"}`.

Reuse the same `ACCESS_TOKEN` for as many calls as needed, until it expires after 5 minutes.

## Step 6: SDEP (machine)

For example (STR):

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

## Step 7: Rotate Keys (admin)

---

### 7a. Local

Delete the generated private key and rerun local setup:

```bash
rm tmp/*.private.pem
make keycloak-generate-machine-clients
make keycloak-configure
```

---

### 7b. PRE, PRD

Rotate a key by coordinating the public-key update with SDEP:

1. Generate a new private/public key pair.
2. Send the new public key to SDEP.
3. Wait for SDEP to assign and confirm the new `kid`.
4. Start signing new client-signed JWTs with the new private key and `kid`.
5. Keep the old private key only until SDEP confirms it is no longer accepted.
