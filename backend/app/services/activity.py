"""Activity business service.

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes (session.flush()), never commits

Pattern:
- API layer: Transaction boundary (auto-commit via dependency)
- Service layer: Business logic (no transaction management)
- CRUD layer: Data access (flush only, no commits)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import activity as activity_crud


async def count_activity(session: AsyncSession) -> int:
    """
    Count all activities.

    Args:
        session: Async database session

    Returns:
        Total number of activity records
    """
    return await activity_crud.count(session)


async def count_activity_by_competent_authority(
    session: AsyncSession, competent_authority_id: str
) -> int:
    """
    Count activities for a competent authority.

    Business logic for counting activities filtered by competent authority.

    Transaction Management:
    - Uses read-only session (no transaction needed for queries)
    - Service contains only business logic

    Args:
        session: Async database session (read-only)
        competent_authority_id: Competent authority ID string (e.g., "0363")

    Returns:
        Total number of activity records for the given competent authority
    """
    return await activity_crud.count_by_competent_authority_id(
        session, competent_authority_id
    )


async def get_activity_list(
    session: AsyncSession,
    competent_authority_id: str,
    offset: int = 0,
    limit: int | None = None,
) -> list[dict]:
    """
    Get activity list for a competent authority.

    Business logic for retrieving activities filtered by competent authority.
    Returns data in dictionary format for API layer serialization.

    Transaction Management:
    - Uses read-only session (no transaction needed for queries)
    - Service contains only business logic

    Args:
        session: Async database session (read-only)
        competent_authority_id: Competent authority ID string (e.g., "0363")
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)

    Returns:
        List of dictionaries containing activities
    """
    # Get activities from CRUD layer
    activity_list = await activity_crud.get_by_competent_authority_id(
        session,
        competent_authority_id,
        offset=offset,
        limit=limit,
    )

    # Convert SQLAlchemy models to dictionaries for API layer
    # Platform and Area information accessed via relationships
    # Return functional IDs (UUIDs), never expose technical IDs
    return [
        {
            "activity_id": activity.activity_id,  # Functional UUID
            "activity_name": activity.activity_name,  # Functional name (optional)
            "status": activity.status.value,
            "platform_id": activity.platform.platform_id,  # Functional ID via relationship
            "platform_name": activity.platform.platform_name,  # Name via relationship
            "url": activity.url,
            "address_thoroughfare": activity.address_thoroughfare,
            "address_locator_designator_number": activity.address_locator_designator_number,
            "address_locator_designator_letter": activity.address_locator_designator_letter,
            "address_locator_designator_addition": activity.address_locator_designator_addition,
            "address_post_code": activity.address_post_code,
            "address_post_name": activity.address_post_name,
            "address_full_address": activity.address_full_address,
            "registration_number": activity.registration_number,
            "area_id": activity.area.area_id,  # Functional UUID via relationship
            "competent_authority_id": activity.area.competent_authority.competent_authority_id,
            "competent_authority_name": activity.area.competent_authority.competent_authority_name,
            "number_of_guests": activity.number_of_guests,
            "country_of_guests": activity.country_of_guests,
            "temporal_start_date_time": activity.temporal_start_date_time,
            "temporal_end_date_time": activity.temporal_end_date_time,
            "created_at": activity.created_at,
        }
        for activity in activity_list
    ]
