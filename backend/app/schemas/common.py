"""Common schema helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, Field

FUNCTIONAL_ID_PATTERN = r"^[A-Za-z0-9-]+$"
_FUNCTIONAL_ID_RE = re.compile(FUNCTIONAL_ID_PATTERN)
CLIENT_ID_PATTERN = r"^[A-Za-z0-9._-]+$"
_CLIENT_ID_RE = re.compile(CLIENT_ID_PATTERN)
UTC_DATETIME_VALIDATION_MESSAGE = (
    "Datetime must be expressed in UTC with offset Z or +00:00"
)

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
    if not value or len(value) > 64 or not _CLIENT_ID_RE.match(value):
        raise ValueError(
            f"client_id must be 1-64 characters matching {CLIENT_ID_PATTERN}, got: '{value}'"
        )


__all__ = [
    "CLIENT_ID_PATTERN",
    "FUNCTIONAL_ID_PATTERN",
    "UTC_DATETIME_VALIDATION_MESSAGE",
    "FunctionalId",
    "OptionalFunctionalId",
    "UtcDateTime",
    "require_utc_datetime",
    "validate_client_id",
]
