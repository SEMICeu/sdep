"""Error response schemas for consistent API error formatting."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Detail of a single error."""

    model_config = ConfigDict(title="Error.Detail")

    msg: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error type identifier")
    loc: list[str | int] | None = Field(
        default=None, description="Location of the error (e.g. ['body', 'fieldName'])"
    )


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    model_config = ConfigDict(title="Error.Response")

    detail: list[ErrorDetail] = Field(..., description="List of error details")
