<h1>SDEP-NL - pre-production</h1>

Welcome to the **SDEP-NL Pre-Production (PRE) environment**. As an **integration partner** testing SDEP, you can use this environment:

- To validate your integration before moving to SDEP-NL production
- To pre-validate your integration against the harmonized short-term rental API, before moving to the SDEP in your country

See https://pre-sdep.minvro.nl/api/docs.

**Disclaimer**: For end-to-end testing per country, always contact your **national SDEP representative** for guidance on deployment, integrations, and operations.

---

<h2>Table of contents</h2>

- [Introduction](#introduction)
  - [SDEP](#sdep)
  - [Authentication](#authentication)
  - [ID-management, idempotency and versioning](#id-management-idempotency-and-versioning)
- [Get access](#get-access)
  - [Generate keypair](#generate-keypair)
  - [Contact team SDEP-NL](#contact-team-sdep-nl)
  - [Receive connection info](#receive-connection-info)
- [Ask questions](#ask-questions)

## Introduction

### SDEP

The **Single Digital Entry Point (SDEP)** is established in accordance with [EU legislation](https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng) for short-term rental data exchange.

The SDEP repository contains:

- The **EU-harmonized API specification** for short-term rental platforms (**STR**)
- The **NL-specific API specification** for competent authorities (**CA**) and statistics authorities (**STA**)
- The **NL-specific reference implementation**

The reference implementation is deployed in the **SDEP-NL Pre-Production (PRE)** environment, enabling integration partners to perform end-to-end testing before moving to production, or before moving to their own national implementation.

https://pre-sdep.minvro.nl/api/docs

The NL-specific API specification and reference implementation can also serve as a blueprint for other national deployments.

In PRE, only **anonymized data** should be used; a daily cleanup removes any residual test data.

---

### Authentication

SDEP is an **API-first application** designed for **machine-to-machine (M2M) integrations**.

For machine authentication, SDEP supports **OAuth 2.0** with the **Client Credentials Grant**.

The Client Credentials Grant itself supports two **client authentication methods**, both on the same `/token` endpoint:

- **Client ID & Secret**
- **Client-Signed JWT**

SDEP-NL PRE supports both authentication methods.

- **Client ID & Secret**
  - This is the default.
  - No additional setup is required on your side.
  - It allows you to easily authenticate and use the Swagger UI with a client ID and client secret.
  - It is used for testing purposes only.
- **Client-Signed JWT**
  - This is the most secure option.
  - It requires you to setup a private/public key pair upfront, and submit the public key to team SDEP-NL.
  - It still allows you to authenticate and use the Swagger UI (after you programmatically acquired a `Bearer` token).
  - It is used to test (simulate) the behaviour in the production environment.
  - See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance.

> Contrary to PRE, the SDEP-NL production environment (PRD) only supports client-signed JWT authentication: see [Getting started in PRD](./GET_STARTED_PRD.md).

> National SDEP implementations are free to adopt either authentication method; this does not impact the API.

> To explore both authentication methods locally, see [Fullstack](../README.md#fullstack).

---

### ID-management, idempotency and versioning

Every area, listing and activity has a **functional ID** (`areaId`, `listingId`, `activityId`).

As competent authority (**CA**) or short-term rental platform (**STR**), you can either:

- **Create (and submit) functional IDs by yourself**
  - Suggestion: random UUID v4, or deterministic UUID v5/v8 ([RFC 9562](https://www.rfc-editor.org/rfc/rfc9562))
- **Let SDEP create the functional IDs** (you leave them out on initial submission)
  - SDEP will generate and return the IDs (as deterministic UUID v8)

In either case it is recommended:

- **Keep the returned functional IDs**
- You need them in case of updating or correcting records later on (versioning)

---

What happens when you submit a record:

| When        | With functional ID            | With content (other fields) as ... | Result                                                                            |
| ----------- | ----------------------------- | ---------------------------------- | --------------------------------------------------------------------------------- |
| Submitted   | Empty (ID is created by SDEP) | New                                | A new record, new ID is created and returned by SDEP                              |
| Resubmitted | Empty (ID is created by SDEP) | Same as before                     | No new record, same ID is returned by SDEP (**idempotency**)                      |
| Resubmitted | Empty (ID is created by SDEP) | Different from before              | A new record, new ID is created and returned by SDEP                              |
| Submitted   | New, as created by you        | New                                | A new record, the supplied ID is returned by SDEP                                 |
| Resubmitted | Existing **[1]**              | Same as before                     | No new record, same ID is returned by SDEP (**idempotency**)                      |
| Resubmitted | Existing                      | Different from before              | A new version of the record (**versioning**), same ID is returned by SDEP **[2]** |

[1] Earlier created by SDEP and kept by you, or earlier created by you.

[2] This represents an update or correction, e.g. a corrected shapefile for an area (CA), or another number of guests for an activity (STR). A listing can only be corrected while it is `pending`.

---

It is recommended to create your own functional IDs.

Motivation:

- You know the ID before you send: when the response gets lost, you can still resend, correct or cancel the record without waiting for SDEP's answer
- Two different records with exactly the same data can stay separate: without an ID, SDEP gives them one generated ID, so they become one record
- A new random check of the same listing only needs a new ID: without an ID, an identical listing returns the stored one, and no new check starts

Suggested approach:

- Generate a UUID for each new record, e.g. random UUIDv4 or deterministic UUIDv5/v8 ([RFC 9562](https://www.rfc-editor.org/rfc/rfc9562))
- Store it, and use the same ID for every update or correction of that record

In short: one record, one ID, for its whole lifecycle.

Details: [ID management](./ARCHITECTURE_TECH.md#id-management) and [Idempotency](./ARCHITECTURE_TECH.md#idempotency).

## Get access

Take the following steps to **get access to the SDEP-NL pre-production (PRE)** environment.

---

### Generate keypair

See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for **guidance**.

---

### Contact team SDEP-NL

**Inquire contact details for team SDEP-NL** (email address) at <https://pre-sdep.minvro.nl/api/docs>.

**Send an email** to SDEP-NL containing the following contact details for your **technical representative**:

- **Technical representative’s email address**: used for onboarding and operational communication.
- **Technical representative’s phone number**: used for onboarding and operational communication.

Also include in the email:

- **Your public key**: used to authenticate your client through client-signed JWT
  - See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance
- **Your role**: used to grant the appropriate API permissions
  - Competent authority (CA)
  - Short-term rental platform (STR)
  - Statistics authority (STA)
  - Listing screening authority (LSA)
  - Listing monitoring authority (LMA)
  - Activity monitoring authority (AMA)

---

### Receive connection info

From team SDEP-NL, you will receive connection info for both authentication methods:

- **Client ID & secret**: to support **client-secret authentication**
- **Token request values**: to support **client-signed JWT**

**One client per organization**: each competent authority (CA) and each short-term rental platform (STR) gets exactly one client.

- All your systems use that one client, and share its credentials.
- A second client is not linked to your organization: SDEP treats it as a separate CA or platform, with its own ID and its own data.

See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for applying these to the SDEP API.

## Ask questions

If you have any questions, feel free to reach out at the above contact details.

Best regards,
**Team SDEP-NL**
