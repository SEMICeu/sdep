"""Validation error schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValidationError(BaseModel):
    """Validation error detail schema"""

    model_config = ConfigDict(title="validation.ValidationError")

    msg: str = Field(
        ...,
        description="Error message",
        examples=["String should have at most 8 characters"],
    )
    type: str = Field(
        ...,
        description="Error type",
        examples=["string_too_long"],
    )


class BadRequestError(BaseModel):
    """Bad request error detail schema for query parameter validation"""

    model_config = ConfigDict(title="validation.BadRequestError")

    msg: str = Field(
        ...,
        description="Error message",
        examples=["Input should be greater than or equal to 0"],
    )
    type: str = Field(
        ...,
        description="Error type",
        examples=["greater_than_equal"],
    )


class HTTPValidationError(BaseModel):
    """HTTP validation error response schema (422 - body validation)"""

    model_config = ConfigDict(title="validation.HTTPValidationError")

    detail: list[ValidationError] = Field(..., description="List of validation errors")


class HTTPBadRequestError(BaseModel):
    """HTTP bad request error response schema (400 - query parameter validation)"""

    model_config = ConfigDict(title="validation.HTTPBadRequestError")

    detail: list[BadRequestError] = Field(..., description="List of validation errors")
