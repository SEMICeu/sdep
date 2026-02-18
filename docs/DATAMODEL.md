<h1>Data Model</h1>

This class model represents the SDEP **internal view** (implementation).

The OpenAPI/Swagger API docs expose this model as the **external view**.

**Machine clients** should ONLY look at the **external view.**

<h2>Table of Contents</h2>

- [Classes](#classes)
  - [Competent Authority](#competent-authority)
  - [Platform](#platform)
  - [Area](#area)
  - [Activity](#activity)
  - [Address (Composite)](#address-composite)
  - [Temporal (Composite)](#temporal-composite)
- [Key Patterns](#key-patterns)
  - [OLTP](#oltp)
  - [ID Management](#id-management)
  - [Versioning](#versioning)
  - [Soft-Delete](#soft-delete)
  - [Authorization](#authorization)

## Classes

![](./DATAMODEL.svg)

- **CompetentAuthority** defines many **Areas** (demanding regulation)
- **Platform** submits many **Activities** (subject to regulation)
- **Activity** references one **Area** (subject to regulation)
- **Activity** embeds one **Address** (rental location)
- **Activity** embeds one **Temporal** (rental time period)
- Activities are routed to CompetentAuthorities based on the referenced Area

### Competent Authority

**Purpose:** Regulates short-term rental in required geographic areas

| Attribute                  | Type      | Constraints                                                                                           |
| :------------------------- | :-------- | :---------------------------------------------------------------------------------------------------- |
| **id**                     | int       | is technical id, mandatory                                                                            |
| **competentAuthorityId**   | string    | is functional id, mandatory, length <= 64, lowercase alphanumeric, is auto-provisioned from JWT claim |
| **competentAuthorityName** | string    | optional, length <= 64, e.g. "Gemeente Amsterdam"                                                     |
| **createdAt**              | datetime  | mandatory, UTC                                                                                        |
| **endedAt**                | datetime  | optional, UTC                                                                                         |
| **areas**                  | reference | optional, references Area                                                                             |

**Class Constraints:**

- UNIQUE (competentAuthorityId, createdAt)

---

### Platform

**Purpose:** Delivers rental activities to competent authorities

| Attribute        | Type      | Constraints                                                                                           |
| :--------------- | :-------- | :---------------------------------------------------------------------------------------------------- |
| **id**           | int       | is technical id, mandatory                                                                            |
| **platformId**   | string    | is functional id, mandatory, length <= 64, lowercase alphanumeric, is auto-provisioned from JWT claim |
| **platformName** | string    | optional, length <= 64, e.g. "Example platform"                                                       |
| **createdAt**    | datetime  | mandatory, UTC                                                                                        |
| **endedAt**      | datetime  | optional, UTC                                                                                         |
| **activities**   | reference | optional, references many Activity                                                                    |

**Class Constraints:**

- UNIQUE (platformId, createdAt)

---

### Area

**Purpose:** Defines a geographic region for short-term rental regulation

| Attribute              | Type        | Constraints                                                                                                             |
| :--------------------- | :---------- | :---------------------------------------------------------------------------------------------------------------------- |
| **id**                 | int         | is technical id, mandatory                                                                                              |
| **areaId**             | string      | is functional id, mandatory, length <= 64, lowercase alphanumeric, is supplied or auto-provisioned otherwise (RFC 6749) |
| **areaName**           | string      | optional, length <= 64, e.g. "Amsterdam-Noord"                                                                          |
| **createdAt**          | datetime    | mandatory, UTC                                                                                                          |
| **endedAt**            | datetime    | optional, UTC                                                                                                           |
| **competentAuthority** | reference   | mandatory, references single Competent Authority                                                                               |
| **filename**           | string      | mandatory, length <= 64, e.g. "Amsterdam.zip"                                                                           |
| **filedata**           | largeBinary | mandatory, max size 1MiB, e.g. a .zip with a collection of ESRI shapefile files                                         |
| **activities**         | reference   | optional, references many Activity                                                                                           |

**Class Constraints:**

- UNIQUE (areaId, competentAuthority, createdAt)

**Notes:**
- The same `areaId` (business identifier, optional) can be resubmitted to create new versions with different timestamps
- The UNIQUE class constraint allows the same `areaId` to be used (owned) by multiple comnpetent authorities

---

### Activity

**Purpose:** Represents an actual rental activity submitted by a platform

| Attribute              | Type            | Constraints                                                                                                             |
| :--------------------- | :-------------- | :---------------------------------------------------------------------------------------------------------------------- |
| **id**                 | int             | is technical id, mandatory                                                                                              |
| **activityId**         | string          | is functional id, mandatory, length <= 64, lowercase alphanumeric, is supplied or auto-provisioned otherwise (RFC 6749) |
| **activityName**       | string          | optional, length <= 64, e.g. "Summer rental"                                                                            |
| **createdAt**          | datetime        | mandatory, UTC                                                                                                          |
| **endedAt**            | datetime        | optional, UTC                                                                                                           |
| **platform**           | reference       | mandatory, references single Platform                                                                                   |
| **area**               | reference       | mandatory, references single Area                                                                                       |
| **url**                | string          | optional, length <= 128, e.g. http://example.com/my-advertisement                                                       |
| **address**            | reference       | mandatory, references single Address composite                                                                                 |
| **registrationNumber** | string          | mandatory, length <= 32                                                                                                 |
| **numberOfGuests**     | int             | optional, min 1, max 1024                                                                                               |
| **countryOfGuests**    | array of string | optional, min 1, max 1024, each ISO 3166-1 alpha-3                                                                      |
| **temporal**           | reference       | mandatory, references single Temporal composite                                                                                |

**Class Constraints:**

- UNIQUE (activityId, platform, createdAt)

**Notes:**
- The same `activityId` (business identifier, optional) can be resubmitted to create new versions with different timestamps
- The UNIQUE class constraint allows the same `activityId` to be used (owned) by multiple platforms
- Each activity must reference an existing area

---

### Address (Composite)

**Purpose:** Structured address information for rental activities

| Attribute      | Type   | Constraints                                                  |
| :------------- | :----- | :----------------------------------------------------------- |
| **street**     | string | mandatory, length <= 64, e.g. Turfmarkt                      |
| **number**     | int    | mandatory, e.g. 147                                          |
| **letter**     | string | optional, length <= 1, e.g. "a"                              |
| **addition**   | string | optional, length <= 10, for example 5h                       |
| **postalCode** | string | mandatory, length <= 8, no spaces, alphanumeric, e.g. 2500EA |
| **city**       | string | mandatory, length <= 64, e.g. Den Haag                       |

---

### Temporal (Composite)

**Purpose:** Time period information for rental activities

| Attribute         | Type     | Constraints                     |
| :---------------- | :------- | :------------------------------ |
| **startDatetime** | datetime | mandatory, year must be >= 2025 |
| **endDatetime**   | datetime | mandatory                       |

**Class Constraints:**

- CHECK (startDatetime < endDatetime)

## Key Patterns

### OLTP
- Single POST
- Single concurrency (no optimistic locking)

### ID Management

Technical IDs
- Represent technical keys, on the **“inside”** (under the hood)
- These are used for referential integrity within the database

Functional IDs
- Represent business identifiers, on the **“outside”**
- Are client-provided (optional), or auto-provisioned otherwise (RFC 9562/4122 UUIDv4)
  - Exception: `platformId` and `competentAuthorityId` (these are auto-provisioned from JWT-claim)
- After a POST, functional IDs are always returned/made visible
- This allows them to be reused in subsequent submissions
- Functional IDs enable versioning (in combination with a timstamp)

https://datatracker.ietf.org/doc/rfc9562/

### Versioning
- Same functional ID can be resubmitted with new timestamp for versioning
  - Entities use `(functionalId, createdAt)` as unique constraint
- Stacking
  - Last becomes current (empty `endedAt`)
  - Previous becomes ended (`endedAt`)
- Enables historical tracking and updates without losing previous versions
- Standard retrieve only yields the current

### Soft-Delete
- When all versions of a functional ID have `endedAt` set, the entity is considered **deactivated**
- Creating a new version with a deactivated functional ID is rejected (HTTP 422)
- This prevents "resurrecting" soft-deleted entities
- The guard applies to: `competentAuthorityId`, `platformId`, `areaId`, and `activityId`

### Authorization
- **Platforms:** Require `sdep_str` role
  - `sdep_write` for POST operations (submitting activities)
  - `sdep_read` for GET operations (reading areas)
- **Competent Authorities:** Require `sdep_ca` role
  - `sdep_write` for POST operations (submitting areas)
  - `sdep_read` for GET operations (reading activities)
