<h1>SDEP NL - Pre-Production</h1>

Welcome to the **SDEP NL pre-production environment (PRE)**.

<h2>Table of Contents</h2>

- [Introduction](#introduction)
- [Get Access](#get-access)

## Introduction

The **Single Digital Entry Point (SDEP)** is established in accordance with [EU legislation](https://eur-lex.europa.eu/eli/reg/2024/1028/oj/eng) for short-term rental data exchange.

This repository contains the EU-harmonized **API specification** and a **reference implementation** that serves as a blueprint for national deployments. See [Introduction](../README.md#introduction), [Specification](../README.md#specification), and [Implementation](../README.md#reference-implementation) for details.

The reference implementation is available in a dedicated **pre-production environment (PRE)**, currently hosted as **SDEP-NL** for the Netherlands, to facilitate end-to-end testing with integration partners.

https://pre-sdep.minvro.nl/api/docs

The PRE environment enables testing of the **EU-harmonized STR component** and the **SDEP-NL-specific CA component**. Only anonymized data should be used; a daily cleanup removes any residual test data.

> **Disclaimer**: For end-to-end testing in your own country, always contact your **national SDEP representative** for guidance on deployment, integrations, and operations.

## Get Access

SDEP is an API-first application designed for machine-to-machine (M2M) integrations.

To request test credentials, please email us using the contact details listed at <https://pre-sdep.minvro.nl/api/docs> and include the following details in your request:

- **Technical email address** - used to share the **machine client ID**
- **Technical phone number** - used to share the **machine client secret**

If you have any questions, please feel free to reach out.

Best regards,
**Team SDEP-NL**
