<h1>SDEP-NL - production</h1>

Welcome to the **SDEP-NL Production (PRD) environment**.

As an **integration partner**, you can use this environment to exchange data with the Netherlands.

See <https://sdep.gov.nl/api/docs>.

**Disclaimer**: for production use per country, always contact your **national SDEP representative** regarding national deployment and operational responsibilities.

---

<h2>Table of contents</h2>

- [Introduction](#introduction)
  - [SDEP](#sdep)
  - [Authentication](#authentication)
- [Get access](#get-access)
  - [Generate keypair](#generate-keypair)
  - [Contact team SDEP-NL](#contact-team-sdep-nl)
  - [Receive connection info](#receive-connection-info)
- [Attention points](#attention-points)
  - [ID-management, idempotency and versioning](#id-management-idempotency-and-versioning)

## Introduction

### SDEP

The **Single Digital Entry Point (SDEP)** is established in accordance with [EU legislation](https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng) for short-term rental data exchange.

The SDEP repository contains:

- The **EU-harmonized API specification** for short-term rental platforms (**STR**)
- The **NL-specific API specification** for the national authorities:
  - Competent authority (**CA**)
  - Activity monitoring authority (**AMA**)
  - Statistics authority (**STA**)
- The **NL-specific reference implementation**

The reference implementation is deployed in the **SDEP-NL Production (PRD)** environment, enabling integration partners to exchange data with the Netherlands.

<https://sdep.gov.nl/api/docs>

The NL-specific API specification and reference implementation can also serve as a blueprint for other national deployments.

---

### Authentication

SDEP is an **API-first application** designed for **machine-to-machine (M2M) integrations**.

For machine authentication, SDEP supports **OAuth 2.0** with the Client Credentials Grant.

The Client Credentials Grant supports **two client authentication methods**, both on the same `/token` endpoint:

- Client-signed JWT
- Client ID & secret

SDEP-NL in PRD supports **client-signed JWT only**.

- It is the most secure option.
- It requires you to setup a private/public key pair upfront, and submit the public key to team SDEP-NL.
- You authenticate by generating a client-signed JWT (from the private key), submitting the JWT to SDEP, and getting a short-lived `Bearer` token.
- Using the short-lived `Bearer` token, you can use the SDEP API programmatically.
- You can also use the Swagger UI interactively, but it still requires the short-lived `Bearer` token (to be pasted into the Swagger UI / Authorize button).
- See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for further guidance.

> National SDEP implementations are free to adopt either authentication method; this does not impact the API.

> To explore both authentication methods locally, see [Fullstack](../README.md#fullstack).

## Get access

Take the following steps to **get access to the SDEP-NL production (PRD)** environment.

---

### Generate keypair

To get access via client-signed JWT, you need to generate a keypair first, see [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for **guidance**.

> It is recommended to use separate keypairs for pre-production (PRE) and production (PRD).

---

### Contact team SDEP-NL

**Find the email address for the SDEP-NL team:**

- Go to [SDEP-NL API Documentation](https://sdep.gov.nl/api/docs).
- Scroll to the bottom of the page and look for the **Contact** section.

**Send email to the SDEP-NL team, and specify your access details:**

- **Your technical representative**: used for onboarding and operational communication
  - Email address
  - Phone number
- **Your role**: used to grant the appropriate API permissions
  - Competent authority (CA)
  - Short-term rental platform (STR)
  - Activity monitoring authority (AMA)
  - Statistics authority (STA)
- **Your public key**: used to authenticate your client through client-signed JWT
  - See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance
- The above will always result in 1 production-account

---

### Receive connection info

From team SDEP-NL, you will receive connection info.

For using it further, see [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md).

---

## Attention points

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

- Less error-prone (more awareness because you already created the ID yourself)
  - Avoiding: "I submit a new version of a record, but forgot to include the ID" > duplicate record
- You know the ID before you send
  - When the response gets lost, you can still resend, correct or cancel the record without waiting for SDEP's answer
- Two different records with exactly the same data can stay separate when required
  - Without an ID, SDEP gives them one generated ID, so they become one record
- A new random check of the same listing only needs a new (your) ID
  - Without an ID, an identical listing returns the stored one, and no new check starts

Suggested approach:

- Generate a UUID for each new record, e.g. random UUIDv4 or deterministic UUIDv5/v8 ([RFC 9562](https://www.rfc-editor.org/rfc/rfc9562))
- Store it, and use the same ID for every update or correction of that record

In short: one record, one ID, for its whole lifecycle.

Details: [ID management](./ARCHITECTURE_TECH.md#id-management) and [Idempotency](./ARCHITECTURE_TECH.md#idempotency).
