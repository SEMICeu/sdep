"""CRUD operations for the Listing model.

Every listing write is a new version (mark the current version ended, insert
the next one), see docs/LISTING_FUNC.md. CRUD only flushes, never commits.
"""

from datetime import datetime

from sqlalchemy import Text, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.crud.platform import all_version_ids
from app.enums import ListingFlag, ListingStatus
from app.models.area import Area
from app.models.competent_authority import CompetentAuthority
from app.models.listing import Listing
from app.models.platform import Platform
from app.schemas.listing import ListingBulkCreate, ListingFilters, ListingScope


def _flags_overlap(dialect_name: str, flags: tuple[ListingFlag, ...]):
    """Any-of filter on the flags array, per dialect (see docs/DATABASE_DIALECTS.md).

    PostgreSQL stores a real array (`&&` overlap); SQLite stores JSON text, so
    match each quoted code as a substring.
    """
    codes = [flag.value for flag in flags]
    if dialect_name == "postgresql":
        return Listing.flags.op("&&")(array(codes))
    # Cast to text, otherwise the LIKE pattern is bound through the array type
    return or_(*[cast(Listing.flags, Text).like(f'%"{code}"%') for code in codes])


def _apply_listing_filters(
    stmt: Select[Listing] | Select[int],
    filters: ListingFilters,
    dialect_name: str,
) -> Select[Listing] | Select[int]:
    # The area_id and competent_authority_id branches rely on the caller having
    # joined Area and CompetentAuthority; the platform_id branch on Platform.
    if filters.created_at_from is not None:
        stmt = stmt.where(Listing.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        stmt = stmt.where(Listing.created_at <= filters.created_at_to)
    if filters.platform_id is not None:
        stmt = stmt.where(Platform.platform_id == filters.platform_id)
    if filters.area_id is not None:
        stmt = stmt.where(Area.area_id == filters.area_id)
    if filters.competent_authority_id is not None:
        stmt = stmt.where(
            CompetentAuthority.competent_authority_id == filters.competent_authority_id
        )
    if filters.flags:
        stmt = stmt.where(_flags_overlap(dialect_name, filters.flags))
    if filters.status is not None:
        stmt = stmt.where(Listing.status == filters.status)
    return stmt


def _apply_scope(
    stmt: Select[Listing] | Select[int], scope: ListingScope
) -> Select[Listing] | Select[int]:
    if scope.platform_client_id is not None:
        stmt = stmt.where(Platform.client_id == scope.platform_client_id)
    if scope.competent_authority_client_id is not None:
        stmt = stmt.where(
            CompetentAuthority.client_id == scope.competent_authority_client_id
        )
    if scope.status is not None:
        stmt = stmt.where(Listing.status == scope.status)
    return stmt


def _current_listings_base(
    stmt: Select[Listing] | Select[int],
) -> Select[Listing] | Select[int]:
    return (
        stmt.join(Platform, Listing.platform_id == Platform.id)
        .join(Area, Listing.area_id == Area.id)
        .join(CompetentAuthority, Area.competent_authority_id == CompetentAuthority.id)
        .where(Listing.ended_at.is_(None))
    )


async def get_current_listings(
    session: AsyncSession,
    *,
    scope: ListingScope,
    offset: int = 0,
    limit: int | None = None,
    filters: ListingFilters | None = None,
) -> list[Listing]:
    """
    Get current listings (ended_at IS NULL) within the audience scope.

    Args:
        session: Async database session
        scope: Fixed audience scope (owner and/or lifecycle status). Keyword-only
            with no default so callers must pass it explicitly - an unscoped read
            is never reached by accident.
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: no limit)
        filters: Optional listing query filters

    Returns:
        List of current Listing instances, newest version first.
    """
    stmt = _current_listings_base(
        select(Listing).options(
            selectinload(Listing.platform),
            selectinload(Listing.area).selectinload(Area.competent_authority),
        )
    )
    stmt = _apply_scope(stmt, scope)
    if filters is not None:
        stmt = _apply_listing_filters(stmt, filters, session.get_bind().dialect.name)
    stmt = stmt.order_by(Listing.created_at.desc(), Listing.id.desc()).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_current_listings(
    session: AsyncSession,
    *,
    scope: ListingScope,
    filters: ListingFilters | None = None,
) -> int:
    """
    Count current listings (ended_at IS NULL) within the audience scope.

    Args:
        session: Async database session
        scope: Fixed audience scope, see get_current_listings
        filters: Optional listing query filters

    Returns:
        Total number of current listings within the scope.
    """
    stmt = _current_listings_base(select(func.count()).select_from(Listing))
    stmt = _apply_scope(stmt, scope)
    if filters is not None:
        stmt = _apply_listing_filters(stmt, filters, session.get_bind().dialect.name)
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_current_by_listing_ids(
    session: AsyncSession,
    listing_ids: list[str],
    platform_id: str,
    *,
    for_update: bool = False,
) -> dict[str, Listing]:
    """
    Get the current version (ended_at IS NULL) of listings for a platform.

    Returns the rows (not just their IDs): the bulk writes check the state and the
    version token on the locked current version, then copy it forward.

    Args:
        session: Async database session
        listing_ids: List of listing functional IDs
        platform_id: Platform public ID, matches every platform version
        for_update: If True, acquire row-level locks (SELECT ... FOR UPDATE)

    Returns:
        Dictionary {listing_id: Listing} for IDs that have a current version
    """
    if not listing_ids:
        return {}

    stmt = (
        select(Listing)
        .options(
            selectinload(Listing.platform),
            selectinload(Listing.area).selectinload(Area.competent_authority),
        )
        .where(
            Listing.listing_id.in_(listing_ids),
            Listing.platform_id.in_(all_version_ids(platform_id)),
            Listing.ended_at.is_(None),
        )
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return {listing.listing_id: listing for listing in result.scalars().all()}


async def bulk_mark_as_ended(
    session: AsyncSession,
    listing_ids: list[str],
    platform_id: str,
) -> None:
    """
    Batch mark current versions of listings as ended (set ended_at = now()).

    A single UPDATE marks all current versions as ended before the bulk INSERT
    creates the next versions.

    Args:
        session: Async database session
        listing_ids: List of listing functional IDs to mark as ended
        platform_id: Platform public ID, matches every platform version
    """
    if not listing_ids:
        return

    stmt = (
        update(Listing)
        .where(
            Listing.listing_id.in_(listing_ids),
            Listing.platform_id.in_(all_version_ids(platform_id)),
            Listing.ended_at.is_(None),
        )
        .values(ended_at=func.now())
    )
    await session.execute(stmt)
    await session.flush()


def build_from_request(
    row: ListingBulkCreate, platform: Platform, area: Area
) -> Listing:
    """Build a `pending` listing version from a validated platform submission.

    The loaded platform and area are assigned, so the response can be built
    without a requery.
    """
    return Listing(
        listing_id=row.listing_id,
        listing_name=row.listing_name,
        status=ListingStatus.pending,
        platform_id=row.platform_technical_id,
        area_id=row.area_technical_id,
        platform=platform,
        area=area,
        url=row.url,
        address_thoroughfare=row.address.thoroughfare,
        address_locator_designator_number=row.address.locator_designator_number,
        address_locator_designator_letter=row.address.locator_designator_letter,
        address_locator_designator_addition=row.address.locator_designator_addition,
        address_post_code=row.address.post_code,
        address_post_name=row.address.post_name,
        address_full_address=row.address.full_address,
        declared_as_short_term_rental=row.declared_as_short_term_rental,
        registration_number=row.registration_number,
        flags=[],
        submitted_at=row.submitted_at,
        screened_at=None,
        acknowledged_at=None,
        created_at=row.created_at,
    )


def build_next_version(
    current: Listing,
    *,
    platform: Platform,
    created_at: datetime,
    status: ListingStatus,
    flags: list[str],
    screened_at: datetime | None,
    acknowledged_at: datetime | None,
) -> Listing:
    """Build the next version of a listing: business data copied, lifecycle fields set.

    `submitted_at` is always copied forward (it belongs to the platform's write).
    `platform` is the current platform version, which differs from
    `current.platform` after a rename.
    """
    return Listing(
        listing_id=current.listing_id,
        listing_name=current.listing_name,
        status=status,
        platform_id=platform.id,
        area_id=current.area_id,
        platform=platform,
        area=current.area,
        url=current.url,
        address_thoroughfare=current.address_thoroughfare,
        address_locator_designator_number=current.address_locator_designator_number,
        address_locator_designator_letter=current.address_locator_designator_letter,
        address_locator_designator_addition=current.address_locator_designator_addition,
        address_post_code=current.address_post_code,
        address_post_name=current.address_post_name,
        address_full_address=current.address_full_address,
        declared_as_short_term_rental=current.declared_as_short_term_rental,
        registration_number=current.registration_number,
        flags=flags,
        submitted_at=current.submitted_at,
        screened_at=screened_at,
        acknowledged_at=acknowledged_at,
        created_at=created_at,
    )


async def bulk_create(
    session: AsyncSession,
    listings: list[Listing],
) -> list[Listing]:
    """
    Insert pre-built listing versions in one flush.

    Only pre-validated rows should be passed (Pydantic, RI and state checks done).

    Args:
        session: Async database session
        listings: Listing versions built by build_from_request / build_next_version

    Returns:
        The same instances, in input order, with IDs populated
    """
    if not listings:
        return []

    session.add_all(listings)
    await session.flush()
    return listings
