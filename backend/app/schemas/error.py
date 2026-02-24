"""Error response schemas for consistent API error formatting."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Detail of a single error."""

    model_config = ConfigDict(title="error.ErrorDetail")

    msg: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error type identifier")


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    model_config = ConfigDict(title="error.ErrorResponse")

    detail: list[ErrorDetail] = Field(..., description="List of error details")
