"""Pydantic schemas for CompetentAuthority API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from app.schemas.common import FunctionalId


class CompetentAuthorityResponse(BaseModel):
    """Competent authority response schema. The private client_id is never exposed."""

    model_config = ConfigDict(
        title="CompetentAuthority.Response",
        from_attributes=True,
        populate_by_name=True,
    )
    competent_authority_id: FunctionalId = Field(
        ...,
        serialization_alias="competentAuthorityId",
        description="Functional ID identifying this competent authority",
        examples=["c4ac8ccf-a281-5789-bad7-28dfac20ca7f"],
    )  # Functional ID
    competent_authority_name: str | None = Field(
        None,
        serialization_alias="competentAuthorityName",
        max_length=64,
        description="Display name (optional) of the competent authority",
        examples=["Amsterdam (inclusief Weesp)"],
    )  # Functional name
    created_at: datetime = Field(
        ...,
        serialization_alias="createdAt",
        description="Timestamp when this competent authority version was created (UTC)",
        examples=["2025-01-01T00:00:00Z"],
    )  # Attribute

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude competentAuthorityName from response when it's None."""
        data = serializer(self)
        if data.get("competentAuthorityName") is None:
            data.pop("competentAuthorityName", None)
        return data


class CompetentAuthorityListResponse(BaseModel):
    """List of competent authorities response schema."""

    model_config = ConfigDict(title="CompetentAuthority.ListResponse")

    competent_authorities: list[CompetentAuthorityResponse] = Field(
        ...,
        serialization_alias="competentAuthorities",
        description="List of competent authorities in context of the current SDEP/member state",
    )


class CompetentAuthorityCountResponse(BaseModel):
    """Count of competent authorities response schema."""

    model_config = ConfigDict(title="CompetentAuthority.CountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of competent authorities in context of the current SDEP/member state",
        examples=[42],
    )  # Attribute
