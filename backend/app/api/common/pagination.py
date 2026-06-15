"""Shared pagination query parameter dependency."""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict


class PaginationParams(BaseModel):
    """Offset/limit pagination parameters used by list endpoints."""

    model_config = ConfigDict(frozen=True)

    offset: int
    limit: int | None


async def pagination_params(
    offset: Annotated[
        int,
        Query(ge=0, description="Number of records to skip (default: 0)"),
    ] = 0,
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=1000,
            description="Maximum number of records to return (default: unlimited, max: 1000 when specified)",
        ),
    ] = None,
) -> PaginationParams:
    """Parse common offset/limit query parameters."""

    return PaginationParams(offset=offset, limit=limit)


async def limited_pagination_params(
    offset: Annotated[
        int,
        Query(ge=0, description="Number of records to skip (default: 0)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=1000,
            description="Maximum number of records to return (default: 1000, max: 1000)",
        ),
    ] = 1000,
) -> PaginationParams:
    """Parse common offset/limit query parameters with a default limit of 1000."""

    return PaginationParams(offset=offset, limit=limit)


PaginationDependency = Annotated[PaginationParams, Depends(pagination_params)]

LimitedPaginationDependency = Annotated[
    PaginationParams, Depends(limited_pagination_params)
]


__all__ = [
    "LimitedPaginationDependency",
    "PaginationDependency",
    "PaginationParams",
    "limited_pagination_params",
    "pagination_params",
]
