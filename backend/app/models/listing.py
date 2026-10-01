"""Listing model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, composite, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.platform import Platform

from app.db.config import Base
from app.enums import ListingStatus
from app.models.address import Address
from app.models.types import StringArray


class Listing(Base):
    """Listing model representing a randomly selected listing (random check).

    A platform submits a listing for screening, SDEP screens it and raises flags,
    the platform acknowledges the flags. Every step is a new version of the same
    listing (listing_id + created_at); no row is ever updated in place.
    See docs/LISTING_FUNC.md for the lifecycle.
    """

    __tablename__ = "listing"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "platform_id",
            "created_at",
            name="uq_listing_listing_id_platform_id_created_at",
        ),
        CheckConstraint(
            "address_locator_designator_letter IS NULL OR address_locator_designator_letter ~ '^[A-Za-z]+$'",
            name="ck_listing_address_locator_designator_letter_alpha",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "listing_id ~ '^[A-Za-z0-9-]+$'",
            name="ck_listing_listing_id_format",
        ).ddl_if(dialect="postgresql"),
        # Flags and status agree: screened-with-flags states carry flags, the
        # others carry none (array_length is NULL for an empty array).
        CheckConstraint(
            "(status IN ('flagged', 'acknowledged') AND coalesce(array_length(flags, 1), 0) >= 1) "
            "OR (status IN ('pending', 'clear') AND coalesce(array_length(flags, 1), 0) = 0)",
            name="ck_listing_status_flags",
        ).ddl_if(dialect="postgresql"),
        # At most one current version per (id, platform version), as for areas
        # (models/area.py). A lost race on a new ID gets a unique violation,
        # which the API returns as 409 (see exceptions/handlers.py).
        Index(
            "uq_listing_current_listing_id_platform",
            "listing_id",
            "platform_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
        # The reads page through current rows, newest first.
        Index(
            "ix_listing_current_created_at",
            "created_at",
            "id",
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
    )

    # Primary key (technical ID, database-internal)
    id: Mapped[int] = mapped_column(primary_key=True)

    # Attributes

    listing_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )  # Functional ID (business-facing, API-exposed, alphanumeric with hyphens, max 64 chars)

    listing_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Functional name (optional, human-readable, max 64 chars)

    status: Mapped[ListingStatus] = mapped_column(
        SAEnum(
            ListingStatus,
            native_enum=True,
            length=16,
            name="listingstatus",
        ),
        nullable=False,
        default=ListingStatus.pending,
    )  # Required lifecycle status: 'pending' (default), 'clear', 'flagged', 'acknowledged'

    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platform.id"), nullable=False, index=True
    )  # Reference - foreign key to Platform

    area_id: Mapped[int] = mapped_column(
        ForeignKey("area.id"), nullable=False, index=True
    )  # Reference - foreign key to Area

    url: Mapped[str] = mapped_column(
        String(2048), nullable=False
    )  # Required, max 2048 (chosen cap, see docs/DATAMODEL_TECH.md), references the listing online

    # Composite attributes - Address (INSPIRE/STR-AP field names)
    address_thoroughfare: Mapped[str] = mapped_column(String(80), nullable=False)
    address_locator_designator_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    address_locator_designator_letter: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    address_locator_designator_addition: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    address_post_code: Mapped[str] = mapped_column(String(10), nullable=False)
    address_post_name: Mapped[str] = mapped_column(String(80), nullable=False)
    address_full_address: Mapped[str] = mapped_column(
        String(328), nullable=False
    )  # 318 (sum of the other address fields) + 5 separators of ", "

    declared_as_short_term_rental: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )  # Required, host self-declaration

    registration_number: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # Optional, for example "REG123456"

    flags: Mapped[list[str]] = mapped_column(
        StringArray, nullable=False
    )  # Required, may be empty; each element a flag code (ListingFlag)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # Set by the platform's submission, copied forward by screening and acknowledgement

    screened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Set by the screening, copied forward by the acknowledgement

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Set by the acknowledgement

    # Audit attributes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )  # Always present, stored in UTC; version timestamp and concurrency token
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Optional, stored in UTC

    # Composites
    address: Mapped[Address] = composite(
        Address,
        address_thoroughfare,
        address_locator_designator_number,
        address_locator_designator_letter,
        address_locator_designator_addition,
        address_post_code,
        address_post_name,
        address_full_address,
    )

    # References
    area: Mapped[Area] = relationship(
        "Area", back_populates="listings"
    )  # Zero to many to one (required)

    platform: Mapped[Platform] = relationship(
        "Platform", back_populates="listings"
    )  # Zero to many to one (required)

    def __repr__(self) -> str:
        """String representation of Listing."""
        return f"<Listing(id={self.id}, listing_id='{self.listing_id}', status='{self.status}', url='{self.url}')>"

    @property
    def area_id_functional(self) -> str:
        """Return the related area functional ID."""
        return self.area.area_id

    @property
    def area_name(self) -> str | None:
        """Return the related area display name."""
        return self.area.area_name

    @property
    def competent_authority_id_functional(self) -> str:
        """Return the related competent authority functional ID."""
        return self.area.competent_authority.competent_authority_id

    @property
    def competent_authority_name(self) -> str | None:
        """Return the related competent authority display name."""
        return self.area.competent_authority.competent_authority_name

    @property
    def platform_id_functional(self) -> str:
        """Return the related platform functional ID."""
        return self.platform.platform_id

    @property
    def platform_name(self) -> str | None:
        """Return the related platform display name."""
        return self.platform.platform_name
