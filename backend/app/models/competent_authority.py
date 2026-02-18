"""CompetentAuthority model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.config import Base

if TYPE_CHECKING:
    from app.models.area import Area


class CompetentAuthority(Base):
    """CompetentAuthority model representing regulatory authorities.

    A Competent Authority (CA) is a regulatory body responsible for short-term rental regulation.
    A Competent Authority can regulate multiple areas.
    The combination of (competent_authority_id, created_at) is unique to enable versioning.
    """

    __tablename__ = "competent_authority"
    __table_args__ = (
        UniqueConstraint(
            "competent_authority_id",
            "created_at",
            name="uq_competent_authority_competent_authority_id_created_at",
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Attributes
    competent_authority_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # Mandatory, unique with created_at (versioning), lowercase alphanumeric with hyphens, max 64 chars, for example "0363" or "sdep-ca0363"

    competent_authority_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Optional, human-readable, max 64 chars, for example "Gemeente Amsterdam"

    # Audit attributes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )  # Always present, stored in UTC
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Optional, stored in UTC

    # References
    areas: Mapped[list[Area]] = relationship(
        "Area", back_populates="competent_authority"
    )  # Zero to many

    def __repr__(self) -> str:
        """String representation of CompetentAuthority."""
        return f"<CompetentAuthority(id={self.id}, competent_authority_id='{self.competent_authority_id}', competent_authority_name='{self.competent_authority_name}')>"
