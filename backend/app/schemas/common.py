"""Common schema helpers."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field

FUNCTIONAL_ID_PATTERN = r"^[A-Za-z0-9-]+$"
_FUNCTIONAL_ID_RE = re.compile(FUNCTIONAL_ID_PATTERN)
CLIENT_ID_PATTERN = r"^[A-Za-z0-9._\-]+$"
_CLIENT_ID_RE = re.compile(CLIENT_ID_PATTERN)

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


def validate_client_id(value: str, field_name: str = "client_id") -> None:
    """Validate a private OAuth client identifier from a JWT claim."""
    if not value or len(value) > 64 or not _CLIENT_ID_RE.match(value):
        raise ValueError(
            f"{field_name} must be 1-64 characters matching {CLIENT_ID_PATTERN}, got: '{value}'"
        )


__all__ = [
    "CLIENT_ID_PATTERN",
    "FUNCTIONAL_ID_PATTERN",
    "FunctionalId",
    "OptionalFunctionalId",
    "validate_client_id",
]
