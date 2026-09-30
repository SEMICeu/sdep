<h1>Activity</h1>

This document provides an overview of SDEP activities.

Status: implemented.

Reference links:

- [Activity (technical)](./ACTIVITY_TECH.md)

<h2>Table of Contents</h2>

- [Goal](#goal)
- [Sequence](#sequence)
- [Data](#data)
- [Process](#process)

## Goal

To support short-term rental **activity regulation**.

## Sequence

```mermaid
sequenceDiagram
    box rgb(219, 234, 254)
    participant STR as STR
    participant SDEP as SDEP
    end
    participant CA as CA
    participant H as Host
    participant AMA as AMA
    participant STA as STA

    STR->>SDEP: 1. GET: regulated areas

    Note over STR: 2. For each regulated area:<br/>select all activities [1].

    STR->>SDEP: 3. POST: activities
    CA->>SDEP: 4. GET: activities [2]
    CA-->>H: 5. Enforce when not compliant [3]<br/>(outside scope of SDEP)
    AMA->>SDEP: 6. GET: activities to monitor
    AMA-->>STR: 7. Enforce when not compliant [4]<br/>(outside scope of SDEP)
    STA->>SDEP: 8. GET: activities to report
    Note over STA: 9. Report to stakeholders<br/>(outside scope of SDEP)
```

---

Legend:

- **STR** - Short-Term Rental Platform
- **SDEP** - Single Digital Entrypoint
- **CA** - Competent Authority
- **Host** - Short-Term Rental Host
- **AMA** - Activity Monitoring Authority
- **STA** - Statistics Authority
- Blue is EU-harmonized, the rest is country-specific
- All actions happen periodically/asynchronously

Footnotes:

- 2.[1] Activities with addresses located within the regulated area.
- 4.[2] Activities with addresses located within a regulated area for which the CA is responsible.
- 5.[3] For example: when hosts exceed an established activity maximum.
- 7.[4] For example: when the number of posted activities is insufficient.

---

Endpoints per step (the contract is in [API](./API_TECH.md#surface), the code is in [Activity (technical)](./ACTIVITY_TECH.md)):

| Step | Actor | Endpoint                                   |
| ---- | ----- | ------------------------------------------ |
| 1.   | STR   | `GET /areas`                               |
| 3.   | STR   | `POST /activities/bulk`                    |
| 4.   | CA    | `GET /activities`, `GET /activities/count` |
| 6.   | AMA   | `GET /activities`, `GET /activities/count` |
| 8.   | STA   | `GET /activities`, `GET /activities/count` |

Steps 2, 5, 7 and 9 have no endpoint: they happen at the actor, outside SDEP.

Process implementations for compliance, monitoring, and reporting are also outside the scope of SDEP.

## Data

See:

- [External API](https://sdep.gov.nl/api/docs)
- [Internal data model](./DATAMODEL_TECH.md)

## Process

Activities are [versioned](./ARCHITECTURE_TECH.md#versioning).

As discussed in the EU technical working group:

- Activity data should only be sent by STR platforms after the stay completion.
- Use the check-out date as the determining factor for which reporting period an activity record belongs to.

Example:

- A stay running from 28 March to 2 April has a check-out date of 2 April
- It falls in the April reporting period and is submitted in the May submission cycle

Rationale:

- This is the most natural and operationally clean rule for platforms
- A stay is only "complete" at check-out, and the data (including duration and guest count) is only fully known at that point
- It also avoids the complexity of splitting multi-month stays across periods

See also https://github.com/SEMICeu/sdep/issues/40.
