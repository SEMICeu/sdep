<h1>Migration Guide: Address Fields (INSPIRE/STR-AP)</h1>

This document describes the breaking change to address field names in the SDEP API,
aligned with the INSPIRE directive and SEMIC STR-AP standard for EU interoperability.

## What Changed

Address fields have been renamed from Dutch BAG-style names to INSPIRE/STR-AP names.
Some maximum length constraints have been widened to accommodate EU-wide address formats.

## Field Mapping

| Old field name | New field name              | Type   | Constraint change        |
| :------------- | :-------------------------- | :----- | :----------------------- |
| `street`       | `thoroughfare`              | string | max 64 -> 80             |
| `number`       | `locatorDesignatorNumber`   | int    | unchanged (>= 1)         |
| `letter`       | `locatorDesignatorLetter`   | string | max 1 -> 10 (optional)   |
| `addition`     | `locatorDesignatorAddition` | string | max 10 -> 128 (optional) |
| `postalCode`   | `postCode`                  | string | max 8 -> 10              |
| `city`         | `postName`                  | string | max 64 -> 80             |

## JSON Payload: Before and After

### Before

```json
{
  "address": {
    "street": "Turfmarkt",
    "number": 147,
    "letter": "a",
    "addition": "5h",
    "postalCode": "2500EA",
    "city": "Den Haag"
  }
}
```

### After

```json
{
  "address": {
    "thoroughfare": "Turfmarkt",
    "locatorDesignatorNumber": 147,
    "locatorDesignatorLetter": "a",
    "locatorDesignatorAddition": "5h",
    "postCode": "2500EA",
    "postName": "Den Haag"
  }
}
```

## Required Client Changes

1. **Update all request payloads** (`POST /str/activities/bulk`):
   - Replace `"street"` with `"thoroughfare"`
   - Replace `"number"` with `"locatorDesignatorNumber"`
   - Replace `"letter"` with `"locatorDesignatorLetter"`
   - Replace `"addition"` with `"locatorDesignatorAddition"`
   - Replace `"postalCode"` with `"postCode"`
   - Replace `"city"` with `"postName"`

2. **Update response parsing** (`GET /ca/activities`):
   - The `address` object in responses uses the same new field names

3. **Review length constraints** if your system validates locally:
   - `thoroughfare` now allows up to 80 characters (was 64)
   - `locatorDesignatorLetter` now allows up to 10 characters (was 1) -- supports multi-character designators like French "bis", "ter"
   - `locatorDesignatorAddition` now allows up to 128 characters (was 10)
   - `postCode` now allows up to 10 characters (was 8) -- accommodates longer EU postal codes
   - `postName` now allows up to 80 characters (was 64)

## Affected Endpoints

| Endpoint                    | Direction | Change                           |
| :-------------------------- | :-------- | :------------------------------- |
| `POST /str/activities/bulk` | Request   | New address field names required |
| `GET /ca/activities`        | Response  | New address field names returned |

## Why

The INSPIRE directive (2007/2/EC) establishes a common framework for spatial data across EU member states.
The SEMIC STR-AP (Short-Term Rental Application Profile) builds on INSPIRE address specifications
to define a standard data model for short-term rental regulation across the EU.

This migration aligns SDEP with these standards, enabling:
- Interoperability with other EU member state rental registration systems
- Compliance with the EU Single Digital Gateway regulation
- Support for address formats beyond the Dutch BAG (e.g., French "bis"/"ter" locator designators)

---

## Addition of `fullAddress` Field

A new required `fullAddress` string field has been added to the Address composite.

- **Type:** `string`, required, max length 318 characters (= 80 + 10 + 10 + 128 + 10 + 80, the sum of the other address field maximums).
- **Semantics:** client-supplied, free-form rendering of the complete address. The server does not derive or normalize the value; it stores whatever the submitting platform provides, up to the length limit.
- **Example:** `"Turfmarkt 147a-5h, 2500EA Den Haag"`.
- **Migration:** Alembic revision `001_initial` includes the column as `NOT NULL` with `VARCHAR(318)`.

---

https://github.com/SEMICeu/sdep/issues/31
