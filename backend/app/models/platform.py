"""Platform model."""

from __future__ import annotations

import uuid
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
    Platforms have a public platformId and a human-readable platformName.
    The combination of (platform_id, client_id, created_at) is unique to enable versioning.
    The client_id is the private authentication identifier used for JWT scoping.
    """

    __tablename__ = "platform"
    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "client_id",
            "created_at",
            name="uq_platform_platform_id_client_id_created_at",
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Attributes
    platform_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, default=lambda: str(uuid.uuid4())
    )  # Public functional ID, generated UUID string

    platform_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Optional, human-readable, max 64 chars, for example "Example.com"

    client_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # Private authentication client ID from JWT, part of owner-scoped versioning, never exposed in API responses

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
