"""Pydantic schemas for Area API requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_serializer,
)


def empty_string_to_none(v: str | None) -> str | None:
    """Convert empty string to None for optional ID fields.

    This allows clients to send "" instead of omitting the field,
    and the ID will be auto-generated as UUID downstream.
    """
    if v == "":
        return None
    return v


class AreaResponse(BaseModel):
    """Area response schema for STR areas."""

    model_config = ConfigDict(
        title="area.AreaResponse",
        from_attributes=True,
        populate_by_name=True,
    )
    area_id: str = Field(
        ...,
        alias="areaId",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9-]+$",
        description="Area functional ID (lowercase alphanumeric with hyphens, max 64 chars)",
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
    )  # Functional ID
    area_name: str | None = Field(
        None,
        alias="areaName",
        max_length=64,
        description="Area name (optional, max 64 chars)",
        examples=["Amsterdam Central"],
    )  # Functional name
    filename: str = Field(
        ...,
        max_length=64,
        description="Area filename",
        examples=["Amsterdam.zip"],
    )  # Attribute
    competent_authority_id: str = Field(
        ...,
        alias="competentAuthorityId",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9-]+$",
        description="Competent authority functional ID who submitted the area (lowercase alphanumeric with hyphens, max 64 chars)",
        examples=["sdep-ca0363"],
    )  # Attribute
    competent_authority_name: str | None = Field(
        None,
        alias="competentAuthorityName",
        max_length=64,
        description="Competent authority name (optional, max 64 chars)",
        examples=["Gemeente Amsterdam"],
    )  # Attribute
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Timestamp when the area was created",
        examples=["2025-01-15T10:30:00Z"],
    )  # Attribute

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude areaName from response when it's None."""
        data = serializer(self)
        if data.get("areaName") is None:
            data.pop("areaName", None)
        return data


class AreasListResponse(BaseModel):
    """List of areas response schema."""

    model_config = ConfigDict(title="area.AreasListResponse")

    areas: list[AreaResponse] = Field(
        ...,
        description="List of areas in context of the current SDEP/member state",
    )


class AreaOwnResponse(BaseModel):
    """Area response schema for CA's own areas (omits competentAuthorityId/Name)."""

    model_config = ConfigDict(
        title="area.AreaOwnResponse",
        from_attributes=True,
        populate_by_name=True,
    )
    area_id: str = Field(
        ...,
        alias="areaId",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9-]+$",
        description="Area functional ID (lowercase alphanumeric with hyphens, max 64 chars)",
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
    )
    area_name: str | None = Field(
        None,
        alias="areaName",
        max_length=64,
        description="Area name (optional, max 64 chars)",
        examples=["Amsterdam Central"],
    )
    filename: str = Field(
        ...,
        max_length=64,
        description="Area filename",
        examples=["Amsterdam.zip"],
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Timestamp when the area was created",
        examples=["2025-01-15T10:30:00Z"],
    )

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude areaName from response when it's None."""
        data = serializer(self)
        if data.get("areaName") is None:
            data.pop("areaName", None)
        return data


class AreasOwnListResponse(BaseModel):
    """List of own areas response schema (for CA)."""

    model_config = ConfigDict(title="area.AreasOwnListResponse")

    areas: list[AreaOwnResponse] = Field(
        ...,
        description="List of areas for the current competent authority",
    )


class AreasCountResponse(BaseModel):
    """Count of areas response schema."""

    model_config = ConfigDict(title="area.AreasCountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of areas in context of the current SDEP/member state",
        examples=[42],
    )  # Attribute
