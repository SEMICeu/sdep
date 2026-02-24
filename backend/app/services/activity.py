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

Exception Handling:
- Service layer raises domain exceptions for business rule violations
- BusinessLogicError for business logic violations (HTTP 422)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import activity as activity_crud
from app.crud import area as area_crud
from app.crud import platform as platform_crud
from app.exceptions.business import BusinessLogicError, InvalidOperationError
from app.models.activity import Activity


async def create_activity(session: AsyncSession, activity_data: dict) -> Activity:
    """
    Create a single activity.

    Looks up or creates the Platform, validates the Area exists, then creates the Activity.
    If a current version exists with the same functional ID (and same platform),
    marks it as ended before creating the new version.

    Args:
        session: Async database session
        activity_data: Dictionary with activity data (from ActivityRequest.to_service_dict())

    Returns:
        Created Activity object

    Raises:
        BusinessLogicError: If the referenced area does not exist
    """
    # Validate area exists by functional ID
    area = await area_crud.get_by_area_id(session, activity_data["area_id"])
    if area is None:
        raise BusinessLogicError(
            f"Area with areaId '{activity_data['area_id']}' not found"
        )

    # Look up or create Platform
    platform_id_str = activity_data["platform_id_str"]
    platform_name = activity_data["platform_name"]
    platform = await platform_crud.get_by_platform_id(session, platform_id_str)

    if platform is None:
        if await platform_crud.exists_any_by_platform_id(session, platform_id_str):
            raise InvalidOperationError(
                f"Platform '{platform_id_str}' has been deactivated"
            )
        platform = await platform_crud.create(
            session=session,
            platform_id=platform_id_str,
            platform_name=platform_name,
        )
    else:
        # Platform exists - mark existing as ended and create new version
        await platform_crud.mark_as_ended(session, platform_id_str)
        platform = await platform_crud.create(
            session=session,
            platform_id=platform_id_str,
            platform_name=platform_name,
        )

    # Mark existing current activity as ended if same functional ID exists
    activity_id = activity_data.get("activity_id")
    if activity_id is not None:
        existing_activity = await activity_crud.get_by_activity_id(session, activity_id)
        if existing_activity is not None:
            await activity_crud.mark_as_ended(
                session, activity_id, existing_activity.platform_id
            )
        elif await activity_crud.exists_any_by_activity_id(session, activity_id):
            raise InvalidOperationError(
                f"Activity '{activity_id}' has been deactivated"
            )

    # Save activity (CRUD only flushes)
    activity_obj = await activity_crud.create(
        session=session,
        activity_id=activity_data.get("activity_id"),
        activity_name=activity_data.get("activity_name"),
        url=activity_data["url"],
        address_street=activity_data["address_street"],
        address_number=activity_data["address_number"],
        address_letter=activity_data.get("address_letter"),
        address_addition=activity_data.get("address_addition"),
        address_postal_code=activity_data["address_postal_code"],
        address_city=activity_data["address_city"],
        registration_number=activity_data["registration_number"],
        area_id=area.id,
        number_of_guests=activity_data["number_of_guests"],
        country_of_guests=activity_data["country_of_guests"],
        temporal_start_date_time=activity_data["temporal_start_date_time"],
        temporal_end_date_time=activity_data["temporal_end_date_time"],
        platform_id=platform.id,
    )

    return activity_obj


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


async def count_activities_by_platform(
    session: AsyncSession, platform_id_str: str
) -> int:
    """
    Count activities for a specific platform (own activities).

    Args:
        session: Async database session (read-only)
        platform_id_str: Platform functional ID string

    Returns:
        Total number of current activities for the given platform
    """
    return await activity_crud.count_by_platform_id_str(session, platform_id_str)


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
            "platform_id": activity.platform.platform_id,  # Functional ID via relationship
            "platform_name": activity.platform.platform_name,  # Name via relationship
            "url": activity.url,
            "address_street": activity.address_street,
            "address_number": activity.address_number,
            "address_letter": activity.address_letter,
            "address_addition": activity.address_addition,
            "address_postal_code": activity.address_postal_code,
            "address_city": activity.address_city,
            "registration_number": activity.registration_number,
            "area_id": activity.area.area_id,  # Functional UUID via relationship
            "number_of_guests": activity.number_of_guests,
            "country_of_guests": activity.country_of_guests,
            "temporal_start_date_time": activity.temporal_start_date_time,
            "temporal_end_date_time": activity.temporal_end_date_time,
            "created_at": activity.created_at,
        }
        for activity in activity_list
    ]


async def get_activities_by_platform(
    session: AsyncSession,
    platform_id_str: str,
    offset: int = 0,
    limit: int | None = None,
) -> list[dict]:
    """
    Get activities for a specific platform (own activities).

    Args:
        session: Async database session
        platform_id_str: Platform functional ID
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)

    Returns:
        List of activity dictionaries (without platformId/Name)
    """
    activities = await activity_crud.get_by_platform_id_str(
        session, platform_id_str, offset=offset, limit=limit
    )

    return [
        {
            "activity_id": activity.activity_id,
            "activity_name": activity.activity_name,
            "url": activity.url,
            "address_street": activity.address_street,
            "address_number": activity.address_number,
            "address_letter": activity.address_letter,
            "address_addition": activity.address_addition,
            "address_postal_code": activity.address_postal_code,
            "address_city": activity.address_city,
            "registration_number": activity.registration_number,
            "area_id": activity.area.area_id,
            "competent_authority_id": activity.area.competent_authority.competent_authority_id,
            "competent_authority_name": activity.area.competent_authority.competent_authority_name,
            "number_of_guests": activity.number_of_guests,
            "country_of_guests": activity.country_of_guests,
            "temporal_start_date_time": activity.temporal_start_date_time,
            "temporal_end_date_time": activity.temporal_end_date_time,
            "created_at": activity.created_at,
        }
        for activity in activities
    ]
