"""Competent authority business service (read-only).

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- CRUD layer only flushes (session.flush()), never commits
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import competent_authority as competent_authority_crud
from app.models.competent_authority import CompetentAuthority


async def get_competent_authorities(
    session: AsyncSession, offset: int = 0, limit: int | None = None
) -> list[CompetentAuthority]:
    """Get current competent authorities, newest first."""
    return await competent_authority_crud.get_all(session, offset=offset, limit=limit)


async def count_competent_authorities(session: AsyncSession) -> int:
    """Count current competent authorities."""
    return await competent_authority_crud.count_current(session)
