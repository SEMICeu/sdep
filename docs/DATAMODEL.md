<h1>Internal Data Model</h1>

This page explains the SDEP **internal data model** (implementation).

**API clients** should ONLY look at the **external data model** (OpenAPI). \
https://sdep.gov.nl/api/docs

<h2>Table of Contents</h2>

- [Data Model](#data-model)
  - [Competent Authority](#competent-authority)
  - [Platform](#platform)
  - [Area](#area)
  - [Activity](#activity)
  - [Address (Composite)](#address-composite)
  - [Temporal (Composite)](#temporal-composite)
  - [AuditLog](#auditlog)

## Data Model

Overview:

- A **CompetentAuthority** regulates geographical **Areas** (typically one)
- A **Platform** submits rental **Activities** (subject to regulation)
- An **Activity** is regulated in an **Area**
- An **Activity** is located on an **Address** (rental location)
- An **Activity** happens during a **Temporal** (rental time period)
- Activities are routed to CompetentAuthorities based on the referenced Area

Diagram:

![](./diagrams/DATAMODEL.svg)

The datamodel is a logical datamodel: references are expressed as objects instead of foreign keys.

### Competent Authority

**Purpose:** Regulates short-term rental in geographic areas

| Attribute                  | Type      | Constraints                                                                                             |
| :------------------------- | :-------- | :------------------------------------------------------------------------------------------------------ |
| **id**                     | int       | required, is technical id                                                                               |
| **competentAuthorityId**   | string    | required, is functional id, length <= 64, alphanumeric with hyphens, is auto-provisioned from JWT claim |
| **competentAuthorityName** | string    | optional, length <= 64, e.g. "Gemeente Amsterdam"                                                       |
| **createdAt**              | datetime  | required, UTC                                                                                           |
| **endedAt**                | datetime  | optional, UTC                                                                                           |
| **areas**                  | reference | optional, references many Area, restricted delete                                                       |

**Class Constraints:**

- UNIQUE (competentAuthorityId, createdAt)

---

### Platform

**Purpose:** Delivers rental activities to competent authorities

| Attribute        | Type      | Constraints                                                                                             |
| :--------------- | :-------- | :------------------------------------------------------------------------------------------------------ |
| **id**           | int       | required, is technical id                                                                               |
| **platformId**   | string    | required, is functional id, length <= 64, alphanumeric with hyphens, is auto-provisioned from JWT claim |
| **platformName** | string    | optional, length <= 64, e.g. "Example platform"                                                         |
| **createdAt**    | datetime  | required, UTC                                                                                           |
| **endedAt**      | datetime  | optional, UTC                                                                                           |
| **activities**   | reference | optional, references many Activity, restricted delete                                                   |

**Class Constraints:**

- UNIQUE (platformId, createdAt)

---

### Area

**Purpose:** Defines a geographic region for short-term rental regulation

| Attribute              | Type        | Constraints                                                                                                                      |
| :--------------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------- |
| **id**                 | int         | required, is technical id                                                                                                        |
| **areaId**             | string      | required, is functional id, length <= 64, alphanumeric with hyphens, is supplied or auto-provisioned otherwise (UUIDv4 RFC 9562) |
| **areaName**           | string      | optional, length <= 64, e.g. "Amsterdam-Noord"                                                                                   |
| **regulation**         | enum        | required, one of {'listing', 'activity', 'all'}, defaults to 'all' when not supplied                                             |
| **createdAt**          | datetime    | required, UTC                                                                                                                    |
| **endedAt**            | datetime    | optional, UTC                                                                                                                    |
| **competentAuthority** | reference   | required, references single Competent Authority                                                                                  |
| **filename**           | string      | required, length <= 64, e.g. "Amsterdam.zip"                                                                                     |
| **filedata**           | largeBinary | required, max size 1MiB, e.g. a .zip with a collection of ESRI shapefile files                                                   |
| **activities**         | reference   | optional, references many Activity, restricted delete                                                                            |

**Class Constraints:**

- UNIQUE (areaId, competentAuthority, createdAt)

**Notes:**

- The same `areaId` (as business identifier) can be resubmitted to create new versions with different timestamps
- The UNIQUE class constraint allows the same `areaId` to be used (owned) by multiple competent authorities
- Regarding `regulation`:
  - Per EU STR Regulation Article 13, there are two types of areas:
  - (1) areas where the registration procedure applies ("listing"), which require platforms to perform random checks and enforce registration numbers on host listings, and
  - (2) areas for which competent authorities have requested activity data ("activity"), which require platforms to forward activity data to the SDEP
  - Depending on Member State context, these areas may not overlap and the authority for defining them may not be the same entity
  - The `regulation` field allows the same Area to be supplied for all use cases: one CA for both purposes ("all"), or multiple CAs supplying the same geographic area for different purposes ("listing" or "activity")
  - See SEMICeu/sdep#5 for the originating discussion

---

### Activity

**Purpose:** Represents an actual rental activity submitted by a platform

| Attribute              | Type            | Constraints                                                                                                                      |
| :--------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| **id**                 | int             | required, is technical id                                                                                                        |
| **activityId**         | string          | required, is functional id, length <= 64, alphanumeric with hyphens, is supplied or auto-provisioned otherwise (UUIDv4 RFC 9562) |
| **activityName**       | string          | optional, length <= 64, e.g. "Summer rental"                                                                                     |
| **status**             | string          | required, lifecycle status; `finished` by default when omitted, or `cancelled`                                                   |
| **createdAt**          | datetime        | required, UTC                                                                                                                    |
| **endedAt**            | datetime        | optional, UTC                                                                                                                    |
| **platform**           | reference       | required, references single Platform                                                                                             |
| **area**               | reference       | required, references single Area                                                                                                 |
| **url**                | string          | required, length <= 128, e.g. http://example.com/my-advertisement                                                                |
| **address**            | reference       | required, references single Address as composite                                                                                 |
| **registrationNumber** | string          | required, length <= 32                                                                                                           |
| **numberOfGuests**     | int             | required, min 1, max 1024                                                                                                        |
| **countryOfGuests**    | array of string | required, min 1, max 1024; each ISO 3166-1 alpha-3 or `N/A`                                                                      |
| **temporal**           | reference       | required, references single Temporal as composite                                                                                |

**Class Constraints:**

- UNIQUE (activityId, platform, createdAt)
- The `numberOfGuests` must equal the number elements in `countryOfGuests`

**Notes:**
- The same `activityId` (as business identifier) can be resubmitted to create new versions with different timestamps
- The UNIQUE class constraint allows the same `activityId` to be used (owned) by multiple platforms
- A later version may change `status` from `finished` to `cancelled` (allowing STRs to make corrections, vice versa is (yet) also allowed)
- Each activity must reference an existing area

---

### Address (Composite)

**Purpose:** Structured address information for rental activities (INSPIRE/STR-AP format)

| Attribute                     | Type   | Constraints                                                        |
| :---------------------------- | :----- | :----------------------------------------------------------------- |
| **thoroughfare**              | string | required, length <= 80, e.g. "Turfmarkt"                           |
| **locatorDesignatorNumber**   | int    | optional, >= 1, e.g. 147                                           |
| **locatorDesignatorLetter**   | string | optional, length <= 10, alphabetic, e.g. "a", "bis"                |
| **locatorDesignatorAddition** | string | optional, length <= 128, e.g. "5h"                                 |
| **postCode**                  | string | required, length <= 10, no spaces, alphanumeric, e.g. 2500EA       |
| **postName**                  | string | required, length <= 80, e.g. Den Haag                              |
| **fullAddress**               | string | required, length <= 318, e.g. "Turfmarkt 147a-5h, 2500EA Den Haag" |

**Notes:**

- For `fullAddress`, max length is 318 = 80 + 10 (unsigned int 32 bit) + 10 + 128 + 10 + 80

---

### Temporal (Composite)

**Purpose:** Time period information for rental activities

| Attribute         | Type     | Constraints                    |
| :---------------- | :------- | :----------------------------- |
| **startDatetime** | datetime | required, year must be >= 2025 |
| **endDatetime**   | datetime | required                       |

**Class Constraints:**

- CHECK (startDatetime < endDatetime)

### AuditLog

**Purpose:** Append-only log of API requests for compliance, security monitoring, and operational accountability

| Attribute          | Type     | Constraints                                                                                                                          |
| :----------------- | :------- | :----------------------------------------------------------------------------------------------------------------------------------- |
| **id**             | int      | required, is technical id                                                                                                            |
| **timestamp**      | datetime | required, UTC, server default now()                                                                                                  |
| **requestId**      | string   | required, UUID4, length <= 64                                                                                                        |
| **roles**          | string   | optional, length <= 256; verified roles (comma-separated), `REJECTED` (401), `UNAUTHORIZED` (403), or `null` (not yet authenticated) |
| **resourceType**   | string   | optional, length <= 32                                                                                                               |
| **action**         | string   | required, length <= 64, semantic action name                                                                                         |
| **httpMethod**     | string   | required, length <= 10                                                                                                               |
| **path**           | string   | required, length <= 512                                                                                                              |
| **httpStatusCode** | int      | required                                                                                                                             |
| **statusCode**     | string   | required, length <= 3, "OK" if < 400 else "NOK"                                                                                      |
| **durationMs**     | int      | optional                                                                                                                             |

**Notes:**
- Append-only: no updates or deletes (except automated retention cleanup)
- Standalone table with no foreign key relationships
- Indexes on: `timestamp`, `request_id`
- **Retention:** rows older than `AUDITLOG_RETENTION` days (default 1) are automatically deleted by a background task
