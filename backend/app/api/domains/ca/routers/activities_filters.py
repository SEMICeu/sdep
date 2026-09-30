"""Query filters for the CA activity list and count endpoints, shared by v1 and v2."""

from typing import Annotated

from fastapi import Query

from app.schemas.activity import ActivityFilters
from app.schemas.common import OptionalFunctionalId, UtcDateTime


async def activity_filters(
    created_at_from: Annotated[
        UtcDateTime | None,
        Query(
            alias="createdAtFrom",
            description="Filter activities whose createdAt timestamp is greater than or equal to this UTC value",
            examples=["2025-06-01T00:00:00Z"],
        ),
    ] = None,
    created_at_to: Annotated[
        UtcDateTime | None,
        Query(
            alias="createdAtTo",
            description="Filter activities whose createdAt timestamp is less than or equal to this UTC value",
            examples=["2025-06-30T23:59:59Z"],
        ),
    ] = None,
    platform_id: Annotated[
        OptionalFunctionalId,
        Query(
            alias="platformId",
            description="Filter by platform functional ID",
            examples=["sdep-str01"],
        ),
    ] = None,
    area_id: Annotated[
        OptionalFunctionalId,
        Query(
            alias="areaId",
            description="Filter by area functional ID",
            examples=["959a7439-7cad-4009-96ec-353b44723db9"],
        ),
    ] = None,
) -> ActivityFilters:
    return ActivityFilters(
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        platform_id=platform_id,
        area_id=area_id,
    )
