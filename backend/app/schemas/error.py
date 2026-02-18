"""Error response schemas for consistent API error formatting."""

from datetime import datetime

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detail of a single error."""

    msg: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error type identifier")

    model_config = {
        "json_schema_extra": {
            "example": {
                "msg": "URL must be unique",
                "type": "duplicate_error",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    detail: list[ErrorDetail] = Field(..., description="List of error details")
    timestamp: datetime = Field(..., description="Timestamp when the error occurred")
    path: str = Field(..., description="API path where the error occurred")
    status_code: int = Field(..., description="HTTP status code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": [{"msg": "Resource not found", "type": "not_found_error"}],
                "timestamp": "2025-01-15T14:22:15Z",
                "path": "/api/v0/str/areas/123",
                "status_code": 404,
            }
        }
    }
