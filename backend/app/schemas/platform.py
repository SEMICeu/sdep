"""Pydantic schemas for Platform API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from app.schemas.common import FunctionalId


class PlatformResponse(BaseModel):
    """Platform response schema. The private client_id is never exposed."""

    model_config = ConfigDict(
        title="Platform.Response",
        from_attributes=True,
        populate_by_name=True,
    )
    platform_id: FunctionalId = Field(
        ...,
        serialization_alias="platformId",
        description="Functional ID identifying this platform",
        examples=["8e70f1e2-4c61-477b-89b8-0dbf25ab8b21"],
    )  # Functional ID
    platform_name: str | None = Field(
        None,
        serialization_alias="platformName",
        max_length=64,
        description="Display name (optional) of the platform",
        examples=["Example.com"],
    )  # Functional name
    created_at: datetime = Field(
        ...,
        serialization_alias="createdAt",
        description="Timestamp when this platform version was created (UTC)",
        examples=["2025-01-01T00:00:00Z"],
    )  # Attribute

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude platformName from response when it's None."""
        data = serializer(self)
        if data.get("platformName") is None:
            data.pop("platformName", None)
        return data


class PlatformListResponse(BaseModel):
    """List of platforms response schema."""

    model_config = ConfigDict(title="Platform.ListResponse")

    platforms: list[PlatformResponse] = Field(
        ...,
        description="List of platforms in context of the current SDEP/member state",
    )


class PlatformCountResponse(BaseModel):
    """Count of platforms response schema."""

    model_config = ConfigDict(title="Platform.CountResponse")

    count: int = Field(
        ...,
        ge=0,
        description="Total number of platforms in context of the current SDEP/member state",
        examples=[12],
    )  # Attribute
