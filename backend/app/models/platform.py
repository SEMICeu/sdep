"""Platform model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.config import Base

if TYPE_CHECKING:
    from app.models.activity import Activity


class Platform(Base):
    """Platform model representing a short-term rental platform.

    A Platform delivers rental activities to the system.
    Platforms are identified by their unique platformId and have a human-readable platformName.
    The combination of (platform_id, created_at) is unique to enable versioning.
    """

    __tablename__ = "platform"
    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "created_at",
            name="uq_platform_platform_id_created_at",
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Attributes
    platform_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # Mandatory, unique with created_at (versioning), lowercase alphanumeric with hyphens, max 64 chars, for example "platform01"

    platform_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Optional, human-readable, max 64 chars, for example "Booking.com"

    # Audit attributes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )  # Always present, stored in UTC
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Optional, stored in UTC

    # Relationships
    activities: Mapped[list[Activity]] = relationship(
        "Activity", back_populates="platform"
    )  # One to many (0..n)

    def __repr__(self) -> str:
        """String representation of Platform."""
        return f"<Platform(id={self.id}, platform_id='{self.platform_id}', platform_name='{self.platform_name}')>"
