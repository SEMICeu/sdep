"""Shared query parameter types for the listing read endpoints.

Each audience declares only the filters it may use (see docs/LISTING_FUNC.md); the
router composes its own ``listing_filters`` dependency from these types, so the
descriptions and examples stay identical across domains.
"""

from typing import Annotated

from fastapi import Query
from fastapi.exceptions import RequestValidationError
from pydantic import TypeAdapter, ValidationError

from app.enums import ListingFlag, ListingStatus
from app.schemas.common import OptionalFunctionalId, UtcDateTime

CreatedAtFromQuery = Annotated[
    UtcDateTime | None,
    Query(
        alias="createdAtFrom",
        description="Filter listings whose createdAt timestamp is greater than or equal to this UTC value",
        examples=["2026-09-01T00:00:00Z"],
    ),
]

CreatedAtToQuery = Annotated[
    UtcDateTime | None,
    Query(
        alias="createdAtTo",
        description="Filter listings whose createdAt timestamp is less than or equal to this UTC value",
        examples=["2026-09-30T23:59:59Z"],
    ),
]

AreaIdQuery = Annotated[
    OptionalFunctionalId,
    Query(
        alias="areaId",
        description="Filter by area functional ID",
        examples=["58ff0814-3aa1-5019-9afb-3cd9f398602c"],
    ),
]

PlatformIdQuery = Annotated[
    OptionalFunctionalId,
    Query(
        alias="platformId",
        description="Filter by platform functional ID",
        examples=["8e70f1e2-4c61-477b-89b8-0dbf25ab8b21"],
    ),
]

CompetentAuthorityIdQuery = Annotated[
    OptionalFunctionalId,
    Query(
        alias="competentAuthorityId",
        description="Filter by competent authority functional ID",
        examples=["c4ac8ccf-a281-5789-bad7-28dfac20ca7f"],
    ),
]


_flags_adapter = TypeAdapter(tuple[ListingFlag, ...])

FlagsQuery = Annotated[
    str | None,
    Query(
        alias="flags",
        description="Filter by flag codes, comma-separated; a listing matches when it carries any of them (`ABS`, `UNK`, `EXP`, `MIS`, `NPR`, `UNX`, `UDS`)",
        examples=["UDS,EXP"],
    ),
]


def parse_flags(value: str | None) -> tuple[ListingFlag, ...] | None:
    """`?flags=UDS,EXP` → (UDS, EXP). An unknown code is a 400, like any bad query value."""
    if value is None:
        return None
    codes = [code.strip() for code in value.split(",") if code.strip()]
    try:
        return _flags_adapter.validate_python(codes)
    except ValidationError as exc:
        errors = [
            {**err, "loc": ("query", "flags", *err["loc"])} for err in exc.errors()
        ]
        raise RequestValidationError(errors) from exc


StatusQuery = Annotated[
    ListingStatus | None,
    Query(
        alias="status",
        description="Filter by lifecycle status (`pending`, `clear`, `flagged`, `acknowledged`)",
        examples=["flagged"],
    ),
]

__all__ = [
    "AreaIdQuery",
    "CompetentAuthorityIdQuery",
    "CreatedAtFromQuery",
    "CreatedAtToQuery",
    "FlagsQuery",
    "PlatformIdQuery",
    "StatusQuery",
    "parse_flags",
]
