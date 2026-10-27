<h1>SDEP-NL - pre-production</h1>

Welcome to the **SDEP-NL Pre-Production (PRE) environment**.

As an **integration partner**, you can use this environment:

- To test your integration before moving to SDEP-NL production
- To test your integration against the harmonized short-term rental API upfront, before moving to the SDEP in your country

See <https://pre-sdep.minvro.nl/api/docs>.

**Disclaimer**: for end-to-end testing per country, always contact your **national SDEP representative** for guidance on deployment, integrations, and operations.

---

<h2>Table of contents</h2>

- [Introduction](#introduction)
  - [SDEP](#sdep)
  - [About authentication](#about-authentication)
  - [About id-management, idempotency and versioning](#about-id-management-idempotency-and-versioning)
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
- The **NL-specific API specification** for the national authorities:
  - Competent authority (**CA**)
  - Activity monitoring authority (**AMA**)
  - Statistics authority (**STA**)
  - Listing screening authority (**LSA**): out of scope yet (alpha, work in progress)
  - Listing monitoring authority (**LMA**): out of scope yet (alpha, work in progress)
- The **NL-specific reference implementation**

The reference implementation is deployed in the **SDEP-NL Pre-Production (PRE)** environment, enabling integration partners to perform end-to-end testing before moving to production, or before moving to their own national implementation.

<https://pre-sdep.minvro.nl/api/docs>

The NL-specific API specification and reference implementation can also serve as a blueprint for other national deployments.

In PRE, only **anonymized data** should be used; a daily cleanup removes any residual test data.

---

### About authentication

SDEP is an **API-first application** designed for **machine-to-machine (M2M) integrations**.

For machine authentication, SDEP supports **OAuth 2.0** with the Client Credentials Grant.

The Client Credentials Grant supports **two client authentication methods**, both on the same `/token` endpoint:

- Client-signed JWT
- Client ID & secret

SDEP-NL in PRE supports **both authentication methods**.

**Client-signed JWT**

- This is the most secure option, as in production.
- It requires you to setup a private/public key pair upfront, and submit the public key to team SDEP-NL.
- You authenticate by generating a client-signed JWT (from the private key), submitting the JWT to SDEP, and getting a short-lived `Bearer` token.
- Using the short-lived `Bearer` token, you can use the SDEP API programmatically.
- See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for further guidance.

**Client ID & secret**

- This is an optional add-on, for easy testing in the Swagger UI.
- It allows you to directly paste your client ID & secret into the Swagger UI / Authorize button.
- There is no need to programmatically get a short-lived `Bearer` token first.
- See [Client ID & secret authentication](./GET_STARTED_CLIENT_ID_SECRET.md) for further guidance.

> The SDEP-NL production environment (PRD) only supports client-signed JWT authentication: see [Getting started in PRD](./GET_STARTED_PRD.md).

> National SDEP implementations are free to adopt either authentication method; this does not impact the API.

> To explore both authentication methods locally, see [Fullstack](../README.md#fullstack).

---

### About id-management, idempotency and versioning

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

## Get access

Take the following steps to **get access to the SDEP-NL pre-production (PRE)** environment.

---

### Generate keypair

To get access via **client-signed JWT**, you need to generate a keypair first.

- See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance.

To get additional access via **client ID & secret**, no preparation is required.

> It is recommended to use separate keypairs for pre-production (PRE) and production (PRD).

---

### Contact team SDEP-NL

**Find the email address for the SDEP-NL team:**

- Go to [SDEP-NL API Documentation](https://pre-sdep.minvro.nl/api/docs).
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
  - Listing screening authority (LSA): out of scope yet (alpha, work in progress)
  - Listing monitoring authority (LMA): out of scope yet (alpha, work in progress)
- **Your authentication public key**: used to authenticate your client through client-signed JWT
  - See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance
- **Your testing preference for authentication**:
  - **Client-signed JWT** (required, as in production)
  - **Client ID & secret** (optional, for easy testing in Swagger UI)
  - Note: both flavours comprise different accounts, they do not see the data of each other
- **Your testing preference for role-play** (only when your role is CA or STR):
  - In **your role only**:
    - You test your part of the API fully
    - You do not test the interaction with your counterpart (STR or CA)
  - In **both roles**:
    - You test your part of the API fully
    - You test the interaction with your counterpart (STR or CA) as well
- The above can result in max. 4 test-accounts (in case you are a CA or STR):
  - 1x client-signed JWT / CA
  - 1x client-signed JWT / STR
  - 1x client ID & secret / CA
  - 1x client ID & secret / STR

---

### Receive connection info

From team SDEP-NL, you will receive connection info.

For using it further, see:

- [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md)
- [Client ID & secret authentication](./GET_STARTED_CLIENT_ID_SECRET.md)

---

### Ask questions

In case of questions, just let us know by email.

Kind regards,

Team SDEP-NL.
