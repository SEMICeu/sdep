"""Area business service.

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- Transaction commits automatically on success, rolls back on exception
- CRUD layer only flushes (session.flush()), never commits

Pattern:
- API layer: Transaction boundary (auto-commit via dependency)
- Service layer: Business logic (no transaction management)
- CRUD layer: Data access (flush only, no commits)

This pattern aligns transaction boundaries with HTTP request boundaries,
making it simple and straightforward for typical REST APIs.

Exception Handling:
- Service layer catches database exceptions and converts to domain exceptions
- DuplicateResourceError for unique constraint violations (HTTP 409)
- ApplicationValidationError for other database constraint violations (HTTP 422)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud import area as area_crud
from app.crud import competent_authority as competent_authority_crud
from app.enums import Regulation
from app.exceptions.business import InvalidOperationError, ResourceNotFoundError
from app.models.area import Area

REGULATION_DEFAULT = Regulation.all


async def get_areas(
    session: AsyncSession, offset: int = 0, limit: int | None = None
) -> list[Area]:
    """
    Get areas in context of the current SDEP/member state.

    Args:
        session: Async database session
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)

    Returns:
        List of current Area objects with competent_authority eagerly loaded.
    """
    # Use eager loading to fetch competent_authority relationship
    stmt = (
        select(Area)
        .options(selectinload(Area.competent_authority))
        .where(Area.ended_at.is_(None))
        # Secondary sort on id ensures deterministic pagination order when rows share the same created_at
        .order_by(Area.created_at.desc(), Area.id.desc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    areas = result.scalars().all()

    return list(areas)


async def count_areas(session: AsyncSession) -> int:
    """
    Count all areas in context of the current SDEP/member state.

    Args:
        session: Async database session

    Returns:
        Total number of areas
    """
    return await area_crud.count(session)


async def count_areas_by_client_id(
    session: AsyncSession,
    client_id: str,
) -> int:
    """
    Count areas for a specific authenticated client.

    Args:
        session: Async database session
        client_id: Client ID from JWT token

    Returns:
        Total number of current areas for the given authenticated client
    """
    return await area_crud.count_by_competent_authority_client_id(session, client_id)


async def get_area_by_id(session: AsyncSession, area_id: str) -> Area | None:
    """
    Get a specific area by functional ID (UUID).

    Args:
        session: Async database session
        area_id: Functional area ID (UUID string)

    Returns:
        Area object, or None if not found.
    """
    area = await area_crud.get_by_area_id(session, area_id)

    if area is None:
        return None

    return area


async def get_area_by_area_id_and_client_id(
    session: AsyncSession,
    area_id: str,
    client_id: str,
) -> Area | None:
    """
    Get a specific area by functional ID, scoped to the authenticated client.

    Args:
        session: Async database session
        area_id: Functional area ID
        client_id: Client ID from JWT token

    Returns:
        Area object, or None if not found / not owned by client
    """
    area = await area_crud.get_by_area_id_and_competent_authority_client_id(
        session, area_id, client_id
    )
    if area is None:
        return None
    return area


async def create_area(
    session: AsyncSession,
    area_id: str | None,
    area_name: str | None,
    filename: str,
    filedata: bytes,
    competent_authority_name: str,
    client_id: str,
    regulation: Regulation | None = None,
) -> Area:
    """
    Create a single area.

    Looks up or creates the CompetentAuthority, then creates the Area.
    If a current version exists with the same functional ID (and same CA),
    marks it as ended before creating the new version.

    Args:
        session: Async database session
        area_id: Optional functional ID (auto-generated UUID if None)
        area_name: Optional display name
        filename: Filename of the uploaded file
        filedata: Binary file data
        client_id: Client ID from JWT token
        competent_authority_name: Competent authority name from JWT token
        regulation: Regulation type (defaults to 'all' when None)

    Returns:
        Created Area object
    """
    if regulation is None:
        regulation = REGULATION_DEFAULT
    public_competent_authority_id: str | None = None
    # Look up or create CompetentAuthority (lock row to prevent concurrent versioning)
    competent_authority = await competent_authority_crud.get_by_client_id(
        session, client_id, for_update=True
    )

    if competent_authority is None:
        if await competent_authority_crud.exists_any_by_client_id(session, client_id):
            message = f"CompetentAuthority client '{client_id}' has been deactivated"
            raise InvalidOperationError(message)
        competent_authority = await competent_authority_crud.create(
            session=session,
            competent_authority_id=public_competent_authority_id,
            client_id=client_id,
            competent_authority_name=competent_authority_name,
        )
    elif competent_authority.competent_authority_name != competent_authority_name:
        # Name changed in JWT claim → version: mark old as ended, create new
        public_competent_authority_id = competent_authority.competent_authority_id
        await competent_authority_crud.mark_as_ended_by_client_id(session, client_id)
        competent_authority = await competent_authority_crud.create(
            session=session,
            competent_authority_id=public_competent_authority_id,
            client_id=client_id,
            competent_authority_name=competent_authority_name,
        )
    # else: CA exists and name unchanged → reuse as-is

    # Mark existing current area as ended if same functional ID exists for THIS CA
    # (lock row to prevent concurrent versioning). Other CAs may keep an area with
    # the same functional ID — they must not be affected.
    if area_id is not None:
        existing_area = await area_crud.get_by_area_id_and_competent_authority_id_str(
            session,
            area_id,
            competent_authority.competent_authority_id,
            for_update=True,
        )
        if existing_area is not None:
            await area_crud.mark_as_ended(
                session, area_id, existing_area.competent_authority_id
            )
        elif await area_crud.exists_any_by_area_id(
            session,
            area_id,
            competent_authority_id_str=competent_authority.competent_authority_id,
        ):
            raise InvalidOperationError(f"Area '{area_id}' has been deactivated")

    # Save area (CRUD only flushes)
    area_obj = await area_crud.create(
        session=session,
        area_id=area_id,
        area_name=area_name,
        regulation=regulation,
        filename=filename,
        filedata=filedata,
        competent_authority_id=competent_authority.id,  # Use the FK (int)
    )
    area_obj.competent_authority = competent_authority

    return area_obj


async def get_areas_by_client_id(
    session: AsyncSession,
    client_id: str,
    offset: int = 0,
    limit: int | None = None,
) -> list[Area]:
    """
    Get areas for a specific authenticated client.

    Args:
        session: Async database session
        client_id: Client ID from JWT token
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)

    Returns:
        List of current Area objects with competent_authority eagerly loaded.
    """
    areas = await area_crud.get_by_competent_authority_client_id(
        session, client_id, offset=offset, limit=limit
    )

    return areas


async def delete_area_by_client_id(
    session: AsyncSession,
    area_id: str,
    client_id: str,
) -> None:
    """
    Soft-delete an area by authenticated client ID.

    Args:
        session: Async database session
        area_id: Area functional ID
        client_id: Client ID from JWT token

    Raises:
        ResourceNotFoundError: If the area doesn't exist, is already ended,
            or belongs to a different CA
    """
    area_obj = await area_crud.get_by_area_id_and_competent_authority_client_id(
        session, area_id, client_id
    )

    if area_obj is None:
        raise ResourceNotFoundError(f"Area '{area_id}' not found")

    await area_crud.mark_as_ended(session, area_id, area_obj.competent_authority_id)
