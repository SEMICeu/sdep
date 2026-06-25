<h1>Internal Data Model</h1>

This page explains the SDEP **internal data model** (implementation).

**API clients** should ONLY look at the **external data model** (OpenAPI). \
https://sdep.gov.nl/api/docs

<h2>Table of Contents</h2>

- [Overview](#overview)
- [Diagram](#diagram)
- [Classes](#classes)
  - [Competent Authority](#competent-authority)
  - [Platform](#platform)
  - [Area](#area)
  - [Activity](#activity)
- [Composites](#composites)
  - [Address](#address)
  - [Temporal](#temporal)
- [AuditLog](#auditlog)

## Overview

- A **CompetentAuthority** regulates geographical **Areas** (typically one)
- A **Platform** submits rental **Activities** (subject to regulation)
- An **Activity** is regulated in an **Area**
- An **Activity** is located on an **Address** (rental location)
- An **Activity** happens during a **Temporal** (rental time period)
- Activities are routed to CompetentAuthorities based on the referenced Area

## Diagram

![](./diagrams/DATAMODEL.svg)

## Classes

The datamodel is a logical datamodel:

- References are expressed as objects instead of foreign keys
- References are implemented by foreign keys to technical ids

Standard attribute pattern:

- Technical id (`id`)
- Functional id (`<class name>Id`)
- Display name (`<class name>Name`)
- ... (other attributes)
- Creation timestamp (`createdAt`)
- Ended-at timestamp (`endedAt`) (soft-delete)

---

### Competent Authority

**Purpose:** Regulates short-term rental in geographic areas

| Attribute                  | Type      | Constraints                                                                       |
| :------------------------- | :-------- | :-------------------------------------------------------------------------------- |
| **id**                     | int       | required, is technical id                                                         |
| **competentAuthorityId**   | string    | required, is functional id, UUIDv4 RFC 9562, always auto-generated, length \<= 64 |
| **competentAuthorityName** | string    | optional, length \<= 64, e.g. "Gemeente Amsterdam"                                |
| **clientId**               | string    | required, name-based reference to `client_id` in JWT claim, length \<= 64         |
| **areas**                  | reference | optional, references many Area, restricted delete                                 |
| **createdAt**              | datetime  | required, UTC                                                                     |
| **endedAt**                | datetime  | optional, UTC                                                                     |

**Class Constraints:**

- UNIQUE (`competentAuthorityId`, `clientId`, `createdAt`) = functional id, owner, version timestamp

**Clarifications:**

- The `competentAuthorityId` is a functional identifier
  - May be exposed in API responses
- `clientId` represents a private authentication identifier
  - Must not be exposed in API responses
- A `competentAuthorityId` is unique only within the scope of a client (`clientId`), and within the context of a specific version (`createdAt`)
  - This allows different clients to use the same `competentAuthorityId` independently
  - This enables clients to submit versioned updates over time
- A competent authority can submit multiple areas
  - In practice, it is expected that most competent authorities will typically submit only one area

---

### Platform

**Purpose:** Delivers rental activities to competent authorities

| Attribute        | Type      | Constraints                                                                       |
| :--------------- | :-------- | :-------------------------------------------------------------------------------- |
| **id**           | int       | required, is technical id                                                         |
| **platformId**   | string    | required, is functional id, UUIDv4 RFC 9562, always auto-generated, length \<= 64 |
| **platformName** | string    | optional, length \<= 64, e.g. "Example platform"                                  |
| **clientId**     | string    | required, name-based reference to `client_id` in JWT claim, length \<= 64         |
| **activities**   | reference | optional, references many Activity, restricted delete                             |
| **createdAt**    | datetime  | required, UTC                                                                     |
| **endedAt**      | datetime  | optional, UTC                                                                     |

**Class Constraints:**

- UNIQUE (`platformId`, `clientId`, `createdAt`) = functional id, owner, version timestamp

**Clarifications:**

- The `platformId` is a functional identifier
  - May be exposed in API responses
- `clientId` represents a private authentication identifier
  - Must not be exposed in API responses
- A `platformId` is unique only within the scope of a client (`clientId`), and within the context of a specific version (`createdAt`)
  - This allows different clients to use the same `platformId` independently
  - This enables clients to submit versioned updates over time
- A platform can submit multiple activities

---

### Area

**Purpose:** Defines a geographic region for short-term rental regulation

| Attribute              | Type        | Constraints                                                                                                                     |
| :--------------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **id**                 | int         | required, is technical id                                                                                                       |
| **areaId**             | string      | required, is functional id, length \<= 64, alphanumeric with hyphens, is supplied or auto-generated otherwise (UUIDv4 RFC 9562) |
| **areaName**           | string      | optional, length \<= 64, e.g. "Amsterdam-Noord"                                                                                 |
| **regulation**         | enum        | required, one of {'listing', 'activity', 'all'}, defaults to 'all' when not supplied                                            |
| **competentAuthority** | reference   | required, references single Competent Authority (owner)                                                                         |
| **filename**           | string      | required, length \<= 64, e.g. "Amsterdam.zip"                                                                                   |
| **filedata**           | largeBinary | required, max size 1MiB, e.g. a .zip with a collection of ESRI shapefile files                                                  |
| **activities**         | reference   | optional, references many Activity, restricted delete                                                                           |
| **createdAt**          | datetime    | required, UTC                                                                                                                   |
| **endedAt**            | datetime    | optional, UTC                                                                                                                   |

**Class Constraints:**

- UNIQUE (`areaId`, `competentAuthority`, `createdAt`) = functional id, owner, version timestamp
- CHECK (`areaId` matches `^[A-Za-z0-9-]+$`)

**Clarifications:**

- The `areaId` is a functional identifier
  - May be exposed in API responses
- An `areaId` is unique only within the scope of a competent authority, and within the context of a specific version (`createdAt`)
  - This allows different competent authorities to use the same `areaId` independently
  - This enables competent authorities to submit versioned updates over time
- Per EU STR Regulation Article 13, there are two types of areas:
  - (1) areas where the registration procedure applies ("listing"), which require platforms to perform random checks and enforce registration numbers on host listings, and
  - (2) areas for which competent authorities have requested activity data ("activity"), which require platforms to forward activity data to the SDEP
  - Depending on Member State context, these areas may not overlap and the authority for defining them may not be the same entity
  - The `regulation` attribute allows the same Area to be supplied for all use cases: one CA for both purposes ("all"), or multiple CAs supplying the same geographic area for different purposes ("listing" or "activity")
  - See SEMICeu/sdep#5 for the originating discussion
- For an area, multiple activities will be submitted (activity regulation)

---

### Activity

**Purpose:** Represents an actual rental activity submitted by a platform

| Attribute              | Type            | Constraints                                                                                                                     |
| :--------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **id**                 | int             | required, is technical id                                                                                                       |
| **activityId**         | string          | required, is functional id, length \<= 64, alphanumeric with hyphens, is supplied or auto-generated otherwise (UUIDv4 RFC 9562) |
| **activityName**       | string          | optional, length \<= 64, e.g. "Summer rental"                                                                                   |
| **status**             | string          | required, lifecycle status; `finished` by default when omitted, or `cancelled`                                                  |
| **platform**           | reference       | required, references single Platform                                                                                            |
| **area**               | reference       | required, references single Area                                                                                                |
| **url**                | string          | required, length \<= 128, e.g. http://example.com/my-advertisement                                                              |
| **address**            | reference       | required, references single Address as composite                                                                                |
| **registrationNumber** | string          | required, length \<= 32                                                                                                         |
| **numberOfGuests**     | int             | required, min 1, max 1024                                                                                                       |
| **countryOfGuests**    | array of string | required, min 1, max 1024; each ISO 3166-1 alpha-3 or `N/A`                                                                     |
| **temporal**           | reference       | required, references single Temporal as composite                                                                               |
| **createdAt**          | datetime        | required, UTC                                                                                                                   |
| **endedAt**            | datetime        | optional, UTC                                                                                                                   |

**Class Constraints:**

- UNIQUE (`activityId`, `platform`, `createdAt`) = functional id, owner, version timestamp
- CHECK (`activityId` matches `^[A-Za-z0-9-]+$`)
- The `numberOfGuests` must equal the number elements in `countryOfGuests`

**Clarifications:**

- The `activityId` is a functional identifier
  - May be exposed in API responses
- An `activityId` is unique only within the scope of a platform, and within the context of a specific version (`createdAt`)
  - This allows different platforms to use the same `activityId` independently
  - This enables platforms to submit versioned updates over time
- A later version may change `status` from `finished` to `cancelled`
  - This allows STRs to make corrections
  - Vice versa is (yet) also allowed
- Each activity must reference an existing area (activity regulation)

## Composites

---

### Address

**Purpose:** Structured address information for rental activities (INSPIRE/STR-AP format)

| Attribute                     | Type   | Constraints                                                         |
| :---------------------------- | :----- | :------------------------------------------------------------------ |
| **thoroughfare**              | string | required, length \<= 80, e.g. "Turfmarkt"                           |
| **locatorDesignatorNumber**   | int    | optional, >= 1, e.g. 147                                            |
| **locatorDesignatorLetter**   | string | optional, length \<= 10, alphabetic, e.g. "a", "bis"                |
| **locatorDesignatorAddition** | string | optional, length \<= 128, e.g. "5h"                                 |
| **postCode**                  | string | required, length \<= 10, no spaces, alphanumeric, e.g. 2500EA       |
| **postName**                  | string | required, length \<= 80, e.g. Den Haag                              |
| **fullAddress**               | string | required, length \<= 318, e.g. "Turfmarkt 147a-5h, 2500EA Den Haag" |

**Class Constraints:**

- CHECK (`locatorDesignatorLetter` is null or alphabetic)

**Clarifications:**

- For `fullAddress`, max length is 318 (= 80 + 10 (unsigned int 32 bit) + 10 + 128 + 10 + 80)

---

### Temporal

**Purpose:** Time period information for rental activities

| Attribute         | Type     | Constraints                    |
| :---------------- | :------- | :----------------------------- |
| **startDatetime** | datetime | required, year must be >= 2025 |
| **endDatetime**   | datetime | required                       |

**Class Constraints:**

- CHECK (startDatetime < endDatetime)
- CHECK (startDatetime year >= 2025)

## AuditLog

**Purpose:** Append-only log of API requests for compliance, security monitoring, and operational accountability

| Attribute          | Type     | Constraints                                                                                                                                                                                       |
| :----------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **id**             | int      | required, is technical id                                                                                                                                                                         |
| **timestamp**      | datetime | required, UTC, server default now()                                                                                                                                                               |
| **requestId**      | string   | required, UUID4, length \<= 64                                                                                                                                                                    |
| **roles**          | string   | optional, length \<= 256; verified roles (comma-separated), or `null` when no token was authenticated (401, or unauthenticated endpoints). The 401/403 distinction is encoded in `httpStatusCode` |
| **resourceType**   | string   | optional, length \<= 32                                                                                                                                                                           |
| **action**         | string   | required, length \<= 64, semantic action name                                                                                                                                                     |
| **httpMethod**     | string   | required, length \<= 10                                                                                                                                                                           |
| **path**           | string   | required, length \<= 512                                                                                                                                                                          |
| **httpStatusCode** | int      | required                                                                                                                                                                                          |
| **statusCode**     | string   | required, length \<= 3, "OK" if < 400 else "NOK"                                                                                                                                                  |
| **durationMs**     | int      | optional                                                                                                                                                                                          |

**Clarifications:**

- Append-only: no updates or deletes (except automated retention cleanup)
- Standalone table with no foreign key relationships
- Indexes on: `timestamp`, `request_id`
- **Retention:** rows older than `AUDITLOG_RETENTION` days (default 1) are automatically deleted by a background task
