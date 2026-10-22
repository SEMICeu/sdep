"""Common schema helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field

FUNCTIONAL_ID_PATTERN = r"^[A-Za-z0-9-]+$"
_FUNCTIONAL_ID_RE = re.compile(FUNCTIONAL_ID_PATTERN)
CLIENT_ID_PATTERN = r"^[A-Za-z0-9._-]+$"
_CLIENT_ID_RE = re.compile(CLIENT_ID_PATTERN)
UTC_DATETIME_VALIDATION_MESSAGE = (
    "Datetime must be expressed in UTC with offset Z or +00:00"
)
# FastAPI drops every None from the OpenAPI document (exclude_none), also inside
# examples. Examples use this marker for a JSON null, see restore_null_examples.
NULL_EXAMPLE = "__null__"


def empty_string_to_none[T](v: T) -> T | None:
    """Read "" as no value, the same as null and an omitted field.

    For optional fields only: an ID is then generated, a default applies, or the
    field stays empty. See docs/ARCHITECTURE_TECH.md, "NULL-values".
    """
    if v == "":
        return None
    return v


def strip_to_none[T](v: T) -> T | None:
    """Trim an optional text; empty after trimming is no value, as "" and null.

    So "  " stores no value, and " Name " is stored as "Name".
    """
    if isinstance(v, str):
        v = v.strip()  # type: ignore[assignment]
    return empty_string_to_none(v)


# An optional text field: trimmed; "", "  ", null and omitted all mean no value.
OptionalText = Annotated[str | None, BeforeValidator(strip_to_none)]

FunctionalId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=FUNCTIONAL_ID_PATTERN,
    ),
]

OptionalFunctionalId = Annotated[
    str | None,
    Field(
        min_length=1,
        max_length=64,
        pattern=FUNCTIONAL_ID_PATTERN,
    ),
]


def require_utc_datetime(value: datetime) -> datetime:
    """Require an aware datetime whose timezone offset is exactly UTC (+00:00)."""
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
        raise ValueError(UTC_DATETIME_VALIDATION_MESSAGE)
    return value


UtcDateTime = Annotated[datetime, AfterValidator(require_utc_datetime)]


def validate_client_id(value: str) -> None:
    """Validate a private OAuth client identifier from a JWT claim."""
    if not value or len(value) > 64 or not _CLIENT_ID_RE.fullmatch(value):
        raise ValueError(
            f"client_id must be 1-64 characters matching {CLIENT_ID_PATTERN}, got: '{value}'"
        )


def supplied_id(raw: object, key: str) -> str | None:
    """Return the ID that a bulk item supplied under `key`, to echo in its result.

    Only a string is echoed: an invalid non-string ID must not break the NOK item.
    """
    value = raw.get(key) if isinstance(raw, dict) else None
    return value if isinstance(value, str) else None


__all__ = [
    "CLIENT_ID_PATTERN",
    "FUNCTIONAL_ID_PATTERN",
    "NULL_EXAMPLE",
    "UTC_DATETIME_VALIDATION_MESSAGE",
    "FunctionalId",
    "OptionalFunctionalId",
    "OptionalText",
    "UtcDateTime",
    "empty_string_to_none",
    "require_utc_datetime",
    "strip_to_none",
    "supplied_id",
    "validate_client_id",
]
