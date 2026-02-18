"""CRUD operations for CompetentAuthority model."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competent_authority import CompetentAuthority


async def create(
    session: AsyncSession,
    competent_authority_id: str,
    competent_authority_name: str,
) -> CompetentAuthority:
    """
    Create a new competent authority.

    Args:
        session: Async database session
        competent_authority_id: Competent authority identifier (64 characters max, unique)
        competent_authority_name: Competent authority name (128 characters max)

    Returns:
        Created CompetentAuthority instance
    """
    competent_authority = CompetentAuthority(
        competent_authority_id=competent_authority_id,
        competent_authority_name=competent_authority_name,
    )
    session.add(competent_authority)
    await session.flush()
    await session.refresh(competent_authority)
    return competent_authority


async def delete(session: AsyncSession, id: int) -> bool:
    """
    Delete a competent authority by id.

    Args:
        session: Async database session
        id: CompetentAuthority id

    Returns:
        True if deleted, False if not found
    """
    competent_authority = await get_by_id(session, id)
    if competent_authority is None:
        return False

    await session.delete(competent_authority)
    await session.flush()
    return True


async def exists(session: AsyncSession, id: int) -> bool:
    """
    Check if a competent authority exists by id.

    Args:
        session: Async database session
        id: CompetentAuthority id

    Returns:
        True if exists, False otherwise
    """
    stmt = select(CompetentAuthority.id).where(CompetentAuthority.id == id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def count(session: AsyncSession) -> int:
    """
    Count all competent authorities.

    Args:
        session: Async database session

    Returns:
        Total number of competent authorities
    """
    stmt = select(func.count()).select_from(CompetentAuthority)
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all(
    session: AsyncSession, offset: int = 0, limit: int | None = None
) -> list[CompetentAuthority]:
    """
    Get current competent authorities with pagination (ended_at IS NULL).

    Args:
        session: Async database session
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)

    Returns:
        List of current CompetentAuthority instances
    """
    stmt = (
        select(CompetentAuthority)
        .where(CompetentAuthority.ended_at.is_(None))
        .order_by(CompetentAuthority.created_at.desc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, id: int) -> CompetentAuthority | None:
    """
    Get a competent authority by id.

    Args:
        session: Async database session
        id: CompetentAuthority id

    Returns:
        CompetentAuthority instance or None if not found
    """
    stmt = select(CompetentAuthority).where(CompetentAuthority.id == id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_competent_authority_id(
    session: AsyncSession,
    competent_authority_id: str,
) -> CompetentAuthority | None:
    """
    Get current competent authority by competent_authority_id (ended_at IS NULL).

    Args:
        session: Async database session
        competent_authority_id: Competent authority identifier

    Returns:
        Current CompetentAuthority instance for the given competent_authority_id, or None if not found
    """
    stmt = select(CompetentAuthority).where(
        CompetentAuthority.competent_authority_id == competent_authority_id,
        CompetentAuthority.ended_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_competent_authority_name(
    session: AsyncSession,
    competent_authority_name: str,
    offset: int = 0,
    limit: int | None = None,
) -> list[CompetentAuthority]:
    """
    Get current competent authorities by competent_authority_name with pagination (ended_at IS NULL).

    Args:
        session: Async database session
        competent_authority_name: Competent authority name
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)

    Returns:
        List of current CompetentAuthority instances matching the competent_authority_name
    """
    stmt = (
        select(CompetentAuthority)
        .where(
            CompetentAuthority.competent_authority_name == competent_authority_name,
            CompetentAuthority.ended_at.is_(None),
        )
        .order_by(CompetentAuthority.created_at.desc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def exists_any_by_competent_authority_id(
    session: AsyncSession,
    competent_authority_id: str,
) -> bool:
    """
    Check if any version of a competent authority exists by functional ID (regardless of ended_at).

    Args:
        session: Async database session
        competent_authority_id: Competent authority functional ID

    Returns:
        True if any version exists, False otherwise
    """
    stmt = (
        select(func.count())
        .select_from(CompetentAuthority)
        .where(CompetentAuthority.competent_authority_id == competent_authority_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one() > 0


async def mark_as_ended(
    session: AsyncSession,
    competent_authority_id: str,
) -> None:
    """
    Mark the current version of a competent authority as ended (set ended_at = now()).

    Args:
        session: Async database session
        competent_authority_id: Competent authority functional ID
    """
    stmt = (
        update(CompetentAuthority)
        .where(
            CompetentAuthority.competent_authority_id == competent_authority_id,
            CompetentAuthority.ended_at.is_(None),
        )
        .values(ended_at=func.now())
    )
    await session.execute(stmt)
    await session.flush()
