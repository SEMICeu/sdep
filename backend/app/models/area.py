"""Area model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.config import Base

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.competent_authority import CompetentAuthority


class Area(Base):
    """Area model representing geographical areas (shapefiles) subject to STR regulation.

    An area constitutes a unit of short-term rental regulation (STR).
    An area is supplied by (regulated by) a competent authority (CA).
    An area is expressed as a binary (shapefile).

    The area_id is a functional identifier that can be optionally
    provided by the competent authority or auto-generated. Combined with created_at,
    it enables versioning.
    """

    __tablename__ = "area"
    __table_args__ = (
        UniqueConstraint(
            "area_id",
            "competent_authority_id",
            "created_at",
            name="uq_area_area_id_competent_authority_id_created_at",
        ),
        CheckConstraint(
            "length(filedata) <= 1048576",
            name="ck_area_filedata_max_size",
        ),
    )

    # Primary key (technical ID, database-internal)
    id: Mapped[int] = mapped_column(primary_key=True)

    # Attributes

    area_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )  # Functional ID (business-facing, API-exposed, lowercase alphanumeric with hyphens, max 64 chars) e.g., "7c9e6679-7425-40de-944b-e07fc1f90ae7"

    area_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Functional name (optional, human-readable, max 64 chars) e.g., "Amsterdam Central"

    competent_authority_id: Mapped[int] = mapped_column(
        ForeignKey("competent_authority.id"), nullable=False, index=True
    )  # Reference - foreign key to CompetentAuthority

    filename: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # Mandatory, for example "Amsterdam.zip"

    filedata: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False
    )  # Mandatory, max size 1 MiB, for example: a .zip with a collection of ESRI shapefile files

    # Audit attributes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )  # Always present, stored in UTC
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Optional, stored in UTC

    # References
    competent_authority: Mapped[CompetentAuthority] = relationship(
        "CompetentAuthority", back_populates="areas"
    )  # One to one (mandatory)

    activities: Mapped[list[Activity]] = relationship(
        "Activity", back_populates="area"
    )  # Zero to many

    def __repr__(self) -> str:
        """String representation of Area."""
        return f"<Area(id={self.id}, area_id='{self.area_id}', filename='{self.filename}')>"
