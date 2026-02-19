"""Activity model."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, composite, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.platform import Platform

from app.db.config import Base
from app.models.address import Address
from app.models.temporal import Temporal


class StringArray(TypeDecorator):
    """Custom type for storing arrays as JSON in SQLite and ARRAY in PostgreSQL."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load the appropriate type based on dialect."""
        match dialect.name:
            case "postgresql":
                return dialect.type_descriptor(ARRAY(String(32)))
            case "sqlite":
                return dialect.type_descriptor(Text())
            case _:
                raise NotImplementedError(f"StringArray not supported for dialect: {dialect.name}")

    def process_bind_param(self, value, dialect):
        """Convert list to JSON string for SQLite."""
        if value is None:
            return None
        match dialect.name:
            case "postgresql":
                return value
            case "sqlite":
                return json.dumps(value)
            case _:
                raise NotImplementedError(f"StringArray not supported for dialect: {dialect.name}")

    def process_result_value(self, value, dialect):
        """Convert JSON string back to list for SQLite."""
        if value is None:
            return None
        match dialect.name:
            case "postgresql":
                return value
            case "sqlite":
                return json.loads(value)
            case _:
                raise NotImplementedError(f"StringArray not supported for dialect: {dialect.name}")


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
            "number_of_guests IS NULL OR (number_of_guests >= 1 AND number_of_guests <= 1024)",
            name="ck_activity_number_of_guests_range",
        ),
        # PostgreSQL-specific constraint for array length (array_length function not available in SQLite)
        CheckConstraint(
            "country_of_guests IS NULL OR (array_length(country_of_guests, 1) >= 1 AND array_length(country_of_guests, 1) <= 1024)",
            name="ck_activity_country_of_guests_length",
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

    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platform.id"), nullable=False, index=True
    )  # Reference - foreign key to Platform

    area_id: Mapped[int] = mapped_column(
        ForeignKey("area.id"), nullable=False, index=True
    )  # Reference - foreign key to Area

    url: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # Optional, for example "http://example.com/my-advertisement"

    # Composite attributes - Address
    address_street: Mapped[str] = mapped_column(String(64), nullable=False)
    address_number: Mapped[int] = mapped_column(Integer, nullable=False)
    address_letter: Mapped[str | None] = mapped_column(String(1), nullable=True)
    address_addition: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address_postal_code: Mapped[str] = mapped_column(String(8), nullable=False)
    address_city: Mapped[str] = mapped_column(String(64), nullable=False)

    registration_number: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # Mandatory, for example "REG123456"

    number_of_guests: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Optional, min 1, max 1024 when provided

    country_of_guests: Mapped[list[str] | None] = mapped_column(
        StringArray, nullable=True
    )  # Optional, min 1, max 1024 when provided

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
        address_street,
        address_number,
        address_letter,
        address_addition,
        address_postal_code,
        address_city,
    )
    temporal: Mapped[Temporal] = composite(
        Temporal, temporal_start_date_time, temporal_end_date_time
    )

    # References
    area: Mapped[Area] = relationship(
        "Area", back_populates="activities"
    )  # Zero to many to one (mandatory)

    platform: Mapped[Platform] = relationship(
        "Platform", back_populates="activities"
    )  # Zero to many to one (mandatory)

    def __repr__(self) -> str:
        """String representation of Activity."""
        return f"<Activity(id={self.id}, activity_id='{self.activity_id}', url='{self.url}', registration_number='{self.registration_number}')>"
