<h1>Design log</h1>

In general, **keep the API as simple and concise as possible**.

*REST APIs are one of the most common kinds of web interfaces available today. Therefore, it's very important to design REST APIs properly so that we won't run into problems down the road.*

*Otherwise, we create problems for clients that use our APIs, which isn’t pleasant and detracts people from using our API.*

*If we don’t follow commonly accepted conventions, then we confuse the maintainers of the API and the clients that use them since it’s different from what everyone expects.*

https://stackoverflow.blog/2020/03/02/best-practices-for-rest-api-design/

<h2>Table of Contents</h2>

- [API](#api)
- [Security](#security)

## API

| #               | Decision                                             | Motivation/example                                                                                                |
| :-------------- | :--------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------- |
| **API&nbsp;01** | Support OpenAPI 3.1.0                                | Swagger 2.0 is legacy - https://swagger.io/specification/                                                         |
| **API&nbsp;02** | All endpoints are self-explanatory/well-documented   |                                                                                                                   |
| **API&nbsp;03** | Use nouns instead of verbs                           | Best practice - https://logius-standaarden.github.io/API-Design-Rules/                                            |
| **API&nbsp;04** | Use plurals for resources that affect collections    | Best practice - https://logius-standaarden.github.io/API-Design-Rules/                                            |
| **API&nbsp;05** | Consistent datamodel [*]                             | Avoid code duplication, only have `Activity`, `Area`, add attribute to indicate "non-reporting records" for CA    |
| **API&nbsp;06** | Consistent endpoints                                 | Have POST/GET "mirrors" - `POST /ca/areas`, `GET /ca/activities` vs. `GET /str/areas`,` POST /str/activities`     |
| **API&nbsp;07** | Consistent pagination                                | Have `offset` and `limit` for all endpoints with (potential) many records                                         |
| **API&nbsp;08** | Syntax validation                                    | Example: `postal code`                                                                                            |
| **API&nbsp;09** | Semantical validation                                | Example: `begin timestamp < end timestamp`                                                                        |
| **API&nbsp;10** | Integrity validation                                 | Example: can only submit activities for existing areas                                                            |
| **API&nbsp;11** | Single record POST                                   | To avoid transaction performance issues and to keep the endpoints simple (as opposed to bulk updates)             |
| **API&nbsp;12** | Logical ordering => readability                      | For POST, request and response follow the same ordering, extra data in response is moved to the end               |
| **API&nbsp;13** | Essentiality                                         | Example: in POST activities, only `areaId` and `competentAuthorityId`, but no `competentAuthorityName`            |
| **API&nbsp;14** | Essentiality/security                                | Example: in POST activities request, no need to include `platformId`                                              |
| **API&nbsp;15** | Consistent HTTP response codes                       | 200, 201, 400, 401, 403, 409, 422                                                                                 |
| **API&nbsp;16** | STR and CA: manage area change                       | These may change over time, SDEP only administrates the changes and exposes the latest "truth"                    |

## Security

| #               | Decision                                                       | Motivation/example                                                                                                           |
| :-------------- | :------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------- |
| **SEC&nbsp;01** | oAuth2 with JWT [*]                                            | Is the standard for trusted machine-to-machine (M2M) interaction - https://datatracker.ietf.org/doc/html/rfc6749#section-4.4 |
| **SEC&nbsp;02** | Smaller platforms can delegate API-invocation to third-parties | Platform arranges data submission with their party; the party becomes registered in SDEP                                     |
