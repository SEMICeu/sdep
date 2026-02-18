"""SDEP Pydantic schemas for health/status endpoints.

Health and status schemas used by common API endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Status(BaseModel):
    """Status response schema"""

    model_config = ConfigDict(title="health.Status")

    status: str | None = Field(None, description="Status message", examples=["ok"])
