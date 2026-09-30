"""Platform business service.

Transaction Management Architecture:
- Service layer contains business logic only (no transaction management)
- API layer manages transaction boundaries via get_async_db dependency
- CRUD layer only flushes (session.flush()), never commits
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import platform as platform_crud
from app.exceptions.business import InvalidOperationError
from app.models.platform import Platform


async def ensure_platform(
    session: AsyncSession, client_id: str, platform_name: str
) -> Platform:
    """Resolve the current platform for a JWT client, creating or versioning it.

    Shared by every STR bulk write. A platform row is created on first contact,
    versioned when the JWT `client_name` changes, and refused when deactivated.

    Args:
        session: Async database session
        client_id: Private platform client ID from the JWT token
        platform_name: Platform name from the JWT token (client_name claim)

    Returns:
        The current Platform instance for the client

    Raises:
        InvalidOperationError: When every version of the platform has ended
    """
    platform = await platform_crud.get_by_client_id(session, client_id)

    if platform is None:
        platform_deactivated = await platform_crud.exists_any_by_client_id(
            session, client_id
        )
        if platform_deactivated:
            raise InvalidOperationError(
                f"Platform client '{client_id}' has been deactivated"
            )
        return await platform_crud.create(
            session=session,
            client_id=client_id,
            platform_name=platform_name,
        )

    if platform.platform_name != platform_name:
        # Name changed in JWT claim → version: mark old as ended, create new
        public_platform_id = platform.platform_id
        await platform_crud.mark_as_ended_by_client_id(session, client_id)
        return await platform_crud.create(
            session=session,
            platform_id=public_platform_id,
            client_id=client_id,
            platform_name=platform_name,
        )

    return platform


async def get_platforms(
    session: AsyncSession, offset: int = 0, limit: int | None = None
) -> list[Platform]:
    """Get current platforms, newest first."""
    return await platform_crud.get_all(session, offset=offset, limit=limit)


async def count_platforms(session: AsyncSession) -> int:
    """Count current platforms."""
    return await platform_crud.count_current(session)
