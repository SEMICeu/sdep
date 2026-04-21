"""Activity model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, composite, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.platform import Platform

from app.db.config import Base
from app.enums import ActivityStatus
from app.models.address import Address
from app.models.temporal import Temporal
from app.models.types import StringArray


class Activity(Base):
    """Activity model representing an actual rental activity.

    An Activity represents an actual rental activity.

    The host has obtained a registration number for the address (conform legislation).

    On the platform, the host has replicated the registration number in each advertisement (unit).
    This covers the case when the address is advertised in parts (units).

    The registration number is consequently replicated in each Activity.

    The activity_id is a functional identifier that can be optionally
    provided by the platform or auto-generated. Combined with created_at, it enables versioning.

    Although registrationNumber is a string, it still is commonly referred to as "number".
    """

    __tablename__ = "activity"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "platform_id",
            "created_at",
            name="uq_activity_activity_id_platform_id_created_at",
        ),
        CheckConstraint(
            "number_of_guests >= 1 AND number_of_guests <= 1024",
            name="ck_activity_number_of_guests_range",
        ),
        # PostgreSQL-specific constraint for array length (array_length function not available in SQLite)
        CheckConstraint(
            "array_length(country_of_guests, 1) >= 1 AND array_length(country_of_guests, 1) <= 1024",
            name="ck_activity_country_of_guests_length",
        ).ddl_if(dialect="postgresql"),
        # PostgreSQL-specific cardinality constraint: numberOfGuests must equal
        # the number of elements in countryOfGuests (DATAMODEL class constraint)
        CheckConstraint(
            "number_of_guests = array_length(country_of_guests, 1)",
            name="ck_activity_guests_cardinality",
        ).ddl_if(dialect="postgresql"),
    )

    # Primary key (technical ID, database-internal)
    id: Mapped[int] = mapped_column(primary_key=True)

    # Attributes

    activity_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )  # Functional ID (business-facing, API-exposed, lowercase alphanumeric with hyphens, max 64 chars), e.g., "550e8400-e29b-41d4-a716-446655440000"

    activity_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Functional name (optional, human-readable, max 64 chars), e.g., "Amsterdam Summer Rental"

    status: Mapped[ActivityStatus] = mapped_column(
        SAEnum(
            ActivityStatus,
            native_enum=True,
            length=16,
            name="activitystatus",
        ),
        nullable=False,
        default=ActivityStatus.finished,
    )  # Required lifecycle status: 'finished' (default) or 'cancelled'

    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platform.id"), nullable=False, index=True
    )  # Reference - foreign key to Platform

    area_id: Mapped[int] = mapped_column(
        ForeignKey("area.id"), nullable=False, index=True
    )  # Reference - foreign key to Area

    url: Mapped[str] = mapped_column(
        String(128), nullable=False
    )  # Required, for example "http://example.com/my-advertisement"

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
    address_full_address: Mapped[str] = mapped_column(String(318), nullable=False)

    registration_number: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # Required, for example "REG123456"

    number_of_guests: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Required, min 1, max 1024

    country_of_guests: Mapped[list[str]] = mapped_column(
        StringArray, nullable=False
    )  # Required, min 1, max 1024; each element ISO 3166-1 alpha-3 or "N/A"; length equals number_of_guests

    # Composite attributes - Temporal
    temporal_start_date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    temporal_end_date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Audit attributes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )  # Always present, stored in UTC
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
    temporal: Mapped[Temporal] = composite(
        Temporal, temporal_start_date_time, temporal_end_date_time
    )

    # References
    area: Mapped[Area] = relationship(
        "Area", back_populates="activities"
    )  # Zero to many to one (required)

    platform: Mapped[Platform] = relationship(
        "Platform", back_populates="activities"
    )  # Zero to many to one (required)

    def __repr__(self) -> str:
        """String representation of Activity."""
        return f"<Activity(id={self.id}, activity_id='{self.activity_id}', url='{self.url}', registration_number='{self.registration_number}')>"
