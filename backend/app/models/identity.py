"""Identity models: one row per functional ID, recording its owner.

Every versioned class has an identity table next to its version table. The
identity row is never ended, so an ID belongs to one owner forever, also after
the resource is deleted (see docs/DATAMODEL_TECH.md, "Identity pattern").

The owner is referenced by its functional ID, not by its technical ID: the
technical ID changes with every owner version.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.config import Base


class CompetentAuthorityIdentity(Base):
    """Identity of a competent authority, owned by one auth client."""

    __tablename__ = "competent_authority_identity"

    # Column names for the generic identity CRUD (see app/crud/identity.py)
    id_column: ClassVar[str] = "competent_authority_id"
    owner_column: ClassVar[str] = "client_id"

    competent_authority_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # Functional ID
    client_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # Owner: private authentication client ID, one competent authority per client
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )  # Always present, stored in UTC


class PlatformIdentity(Base):
    """Identity of a platform, owned by one auth client."""

    __tablename__ = "platform_identity"

    id_column: ClassVar[str] = "platform_id"
    owner_column: ClassVar[str] = "client_id"

    platform_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # Functional ID
    client_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # Owner: private authentication client ID, one platform per client
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )  # Always present, stored in UTC


class AreaIdentity(Base):
    """Identity of an area, owned by one competent authority."""

    __tablename__ = "area_identity"

    id_column: ClassVar[str] = "area_id"
    owner_column: ClassVar[str] = "competent_authority_id"

    area_id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Functional ID
    competent_authority_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("competent_authority_identity.competent_authority_id"),
        nullable=False,
        index=True,
    )  # Owner: functional ID of the competent authority
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )  # Always present, stored in UTC


class ListingIdentity(Base):
    """Identity of a listing, owned by one platform."""

    __tablename__ = "listing_identity"

    id_column: ClassVar[str] = "listing_id"
    owner_column: ClassVar[str] = "platform_id"

    listing_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # Functional ID
    platform_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_identity.platform_id"),
        nullable=False,
        index=True,
    )  # Owner: functional ID of the platform
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )  # Always present, stored in UTC


class ActivityIdentity(Base):
    """Identity of an activity, owned by one platform."""

    __tablename__ = "activity_identity"

    id_column: ClassVar[str] = "activity_id"
    owner_column: ClassVar[str] = "platform_id"

    activity_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # Functional ID
    platform_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_identity.platform_id"),
        nullable=False,
        index=True,
    )  # Owner: functional ID of the platform
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )  # Always present, stored in UTC


type IdentityModel = (
    type[CompetentAuthorityIdentity]
    | type[PlatformIdentity]
    | type[AreaIdentity]
    | type[ListingIdentity]
    | type[ActivityIdentity]
)
