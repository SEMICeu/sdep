<h1>SDEP-NL - Production</h1>

Welcome to the **SDEP-NL production environment (PRD)**.

## About This Guide

**Purpose**: Prepare for access to the SDEP-NL production environment.

**Target audience**: Integration partners connecting to SDEP-NL PRD.

**Outcome after completion**: Request PRD access and connect a production machine client.

## Table of Contents

- [Introduction](#introduction)
- [Prepare](#prepare)
- [Get Access](#get-access)

## Introduction

The **Single Digital Entry Point (SDEP)** is established in accordance with [EU legislation](https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng) for short-term rental data exchange.

This repository contains the EU-harmonized **API specification** and a **reference implementation** that serves as a blueprint for national deployments. See [Introduction](../README.md#introduction), [Specification](../README.md#specification), and [Implementation](../README.md#reference-implementation) for details.

The reference implementation is deployed in **production** (PRD) as **SDEP-NL** for the Netherlands, enabling competent authorities (CA) and short-term rental platforms (STR) to exchange regulated-area and rental-activity data in accordance with EU legislation.

https://sdep.gov.nl/api/docs

The PRD environment includes the **EU-harmonized STR component** and the **SDEP-NL-specific CA and REP components**.

> **Disclaimer**: For production use in your own country, always contact your **national SDEP representative** regarding national deployment and operational responsibilities.

## Prepare

SDEP is an **API-first application** designed for **machine-to-machine (M2M) integrations**.

- **SDEP-NL** uses **oAuth2 with client-signed JWT authentication** for machine clients (most secure)
  - The Swagger **Authorize** button accepts a Bearer token, which is obtained via the client-signed JWT flow (`/token` endpoint)
  - To prepare for the client-signed JWT flow, you need to setup a private/public key pair.
  - To set up a private/public key pair, see [Client-Signed JWT Authentication](./GET_STARTED_CLIENT_SIGNED_JWT.md).

> **National SDEP implementations** can decide on their own which flow they adopt; this does not impact the API

## Get Access

To **request client access for SDEP-NL Production**, please email us, using the contact details listed at <https://sdep.gov.nl/api/docs>.

Include the following details in your request:

- **Technical email address**: used for onboarding and operational contact.
- **Technical phone number**: used for onboarding and operational contact.
- **Role** (are you a competent authority (CA), short-term rental platform (STR), or reporting.statistics office (REP)): used to grant the appropriate API permissions.
- **For client-signed JWT authentication (required)**: your public key in PEM format, used to authenticate your client by verifying the JWTs it signs.

If you have any questions, please feel free to reach out.

Best regards,
**Team SDEP-NL**
