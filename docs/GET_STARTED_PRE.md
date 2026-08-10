<h1>SDEP-NL - Pre-Production</h1>

Welcome to the **SDEP-NL Pre-Production (PRE) environment**. As an **integration partner** testing SDEP, you can use this environment:

- To validate your integration before moving to SDEP-NL production
- To pre-validate your integration against the harmonized short-term rental API, before moving to the SDEP in your country.

> **Disclaimer**: For end-to-end testing per country, always contact your **national SDEP representative** for guidance on deployment, integrations, and operations.

<h2>Table of Contents</h2>

- [Introduction](#introduction)
  - [SDEP](#sdep)
  - [Authentication](#authentication)
- [Get Access](#get-access)
  - [Generate keypair](#generate-keypair)
  - [Contact team SDEP-NL](#contact-team-sdep-nl)
  - [Receive credentials](#receive-credentials)
- [Ask questions](#ask-questions)

## Introduction

---

### SDEP

The **Single Digital Entry Point (SDEP)** is established in accordance with [EU legislation](https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng) for short-term rental data exchange.

The SDEP repository contains:

- The **EU-harmonized API specification** for short-term rental platforms (**STR**)
- The **NL-specific API specification** for competent authorities (**CA**) and reporting/statistics offices (**REP**)
- The **NL-specific reference implementation**

The reference implementation is deployed in the **SDEP-NL Pre-Production (PRE)** environment, enabling integration partners to perform end-to-end testing before moving to production, or before moving to their own national implementation.

In PRE, only **anonymized data** should be used; a daily cleanup removes any residual test data.

The NL-specific API specification and reference implementation can also serve as a blueprint for other national deployments.

https://pre-sdep.minvro.nl/api/docs

---

### Authentication

SDEP is an **API-first application** designed for **machine-to-machine (M2M) integrations**.

For machine authentication, SDEP supports **OAuth 2.0** with the **Client Credentials grant**.

The Client Credentials Grant supports two types of **client authentication**, both on the same `/token` endpoint:

- **Client ID & Secret**
- **Client-Signed JWT**

SDEP-NL PRE supports both authentication types.

- **Client ID & Secret**
  - This is the default.
  - No additional setup is required on your side.
  - It allows you to easily authenticate and use the Swagger UI with a client ID and client secret.
  - It is used for testing purposes only.
- **Client-Signed JWT**
  - This is the most secure option.
  - It requires you to setup a private/public key pair upfront, and submit the public key to team SDEP-NL.
  - It still allows you to authenticate and use the Swagger UI (after you programmatically acquired a `Bearer` token).
  - It is used to test (simulate) the behavior in the production environment.
  - See [Get Started with Client Signed JWT](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance.

> Contrary to PRE, the SDEP-NL production environment (PRD) only supports client-signed JWT authentication: see [Getting Started in PRD](./GET_STARTED_PRD.md).

> National SDEP implementations are free to adopt either authentication method; this does not impact the API.

> To explore both authentication methods locally, see [Fullstack](../README.md#fullstack).

## Get Access

Take the following steps to **get access to the SDEP-NL pre-production (PRE)** environment.

---

### Generate keypair

See [Client-Signed JWT Authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for **guidance**.

---

### Contact team SDEP-NL

**Inquire contact details for team SDEP-NL** (email address) at <https://pre-sdep.minvro.nl/api/docs>.

**Send an email** to SDEP-NL containing the following contact details for your **technical representative**:

- **Technical representative’s email address**: used for onboarding and operational communication.
- **Technical representative’s phone number**: used for onboarding and operational communication.

Also include in the email:

- **Your public key**: used to authenticate your client through client-signed JWT
  - See [Client-Signed JWT Authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for guidance
- **Your Role**: used to grant the appropriate API permissions
  - Competent authority (CA)
  - Short-term rental platform (STR)
  - Reporting statistics office (REP)

---

### Receive credentials

From team SDEP-NL, you will receive:

- **Client ID & secret**: to support **client-secret authentication**
- **Token request values**: to support **client-signed JWT**

See [Client-Signed JWT Authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md) for applying these to the SDEP API.

## Ask questions

If you have any questions, feel free to reach out at the above contact details.

Best regards,
**Team SDEP-NL**
