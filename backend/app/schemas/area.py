"""Pydantic schemas for Area API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_serializer,
)

from app.enums import Regulation
from app.schemas.common import FunctionalId  # noqa: TC001


def empty_string_to_none(v: str | None) -> str | None:
    """Convert empty string to None for optional fields.

    This allows clients (notably the Swagger "--" dropdown option) to send ""
    instead of omitting the field; downstream layers then apply the default.
    """
    if v == "":
        return None
    return v


OptionalRegulation = Annotated[
    Regulation | None,
    BeforeValidator(empty_string_to_none),
]


class AreaResponse(BaseModel):
    """Area response schema."""

    model_config = ConfigDict(
        title="area.AreaResponse",
        from_attributes=True,
        populate_by_name=True,
    )
    area_id: FunctionalId = Field(
        ...,
        alias="areaId",
        description="Area functional ID (alphanumeric with hyphens, max 64 chars)",
        examples=["959a7439-7cad-4009-96ec-353b44723db9"],
    )  # Functional ID
    area_name: str | None = Field(
        None,
        alias="areaName",
        max_length=64,
        description="Area name (optional, max 64 chars)",
        examples=["Amsterdam"],
    )  # Functional name
    regulation: Regulation = Field(
        default=Regulation.all,
        description="Regulation type: listing, activity, or all",
        examples=["all"],
    )
    filename: str = Field(
        ...,
        max_length=64,
        description="Area filename",
        examples=["Amsterdam.zip"],
    )  # Attribute
    competent_authority_id: FunctionalId = Field(
        ...,
        alias="competentAuthorityId",
        description="Functional ID referencing the competent authority that owns the area (alphanumeric with hyphens, max 64 chars)",
        examples=["sdep-ca0363"],
    )  # Attribute
    competent_authority_name: str | None = Field(
        None,
        alias="competentAuthorityName",
        max_length=64,
        description="Competent authority name (optional, max 64 chars)",
        examples=["Amsterdam (inclusief Weesp)"],
    )  # Attribute
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Timestamp when the area was created",
        examples=["2025-01-01T00:00:00Z"],
    )  # Attribute

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude areaName from response when it's None."""
        data = serializer(self)
        if data.get("areaName") is None:
            data.pop("areaName", None)
        return data


class AreaListResponse(BaseModel):
    """List of areas response schema."""

    model_config = ConfigDict(title="area.AreaListResponse")

    areas: list[AreaResponse] = Field(
        ...,
        description="List of areas in context of the current SDEP/member state",
    )


class AreaCountResponse(BaseModel):
    """Count of areas response schema."""

    model_config = ConfigDict(title="area.AreaCountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of areas in context of the current SDEP/member state",
        examples=[42],
    )  # Attribute
