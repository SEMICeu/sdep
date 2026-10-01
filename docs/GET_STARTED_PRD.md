<h1>SDEP-NL - production</h1>

Welcome to the **SDEP-NL Production (PRD) environment**. As an **integration partner**, you can use this environment to exchange data with the Netherlands.

> **Disclaimer**: For production use per country, always contact your **national SDEP representative** regarding national deployment and operational responsibilities.

<h2>Table of contents</h2>

- [Introduction](#introduction)
  - [SDEP](#sdep)
  - [Authentication](#authentication)
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

The reference implementation is deployed in the **SDEP-NL Production (PRD)** environment, enabling integration partners to exchange data with the Netherlands.

https://sdep.gov.nl/api/docs

The NL-specific API specification and reference implementation can also serve as a blueprint for other national deployments.

---

### Authentication

SDEP is an **API-first application** designed for **machine-to-machine (M2M) integrations**.

For machine authentication, SDEP supports **OAuth 2.0** with the **Client Credentials Grant**.

The Client Credentials Grant itself supports two types of **client authentication**, both on the same `/token` endpoint:

- **Client ID & Secret**
- **Client-Signed JWT**

However, SDEP-NL PRD only supports Client-Signed JWT.

- This is the most secure option.
- It requires you to setup a private/public key pair upfront, and submit the public key to team SDEP-NL.
- It allows you to authenticate and use the Swagger UI (after you programmatically acquired a `Bearer` token).
- See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance.

> National SDEP implementations are free to adopt either authentication method; this does not impact the API.

> To explore both authentication methods locally, see [Fullstack](../README.md#fullstack).

## Get access

Take the following steps to **get access to the SDEP-NL production (PRD)** environment.

---

### Generate keypair

See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for **guidance**.

---

### Contact team SDEP-NL

**Inquire contact details for team SDEP-NL** (email address) at <https://sdep.gov.nl/api/docs>.

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

From team SDEP-NL, you will receive connection info for only the **client-signed JWT** authentication method.

**One client per organization**: each competent authority (CA) and each short-term rental platform (STR) gets exactly one client.

- All your systems use that one client, and share its credentials.
- A second client is not linked to your organization: SDEP treats it as a separate CA or platform, with its own ID and its own data.

See [Client-signed JWT authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for applying these to the SDEP API.

## Ask questions

If you have any questions, feel free to reach out at the above contact details.

Best regards,
**Team SDEP-NL**
