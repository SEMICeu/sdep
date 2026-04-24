"""Pydantic schemas for Bulk Activity API requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, model_serializer

from app.schemas.activity import ActivityRequest, ActivityResponse  # noqa: TC001
from app.schemas.error import ErrorResponse  # noqa: TC001

__all__ = [
    "ActivityBulkRequest",
    "ActivityBulkResponse",
    "ActivityBulkResultItem",
]


class ActivityBulkRequest(BaseModel):
    """Bulk activity request schema.

    The `activities` field is typed as `list[ActivityRequest]` for the OpenAPI
    contract, but item-level validation is skipped at request-parse time (via
    `SkipValidation`). This preserves the Application-First Validation flow:
    each item is validated individually in the service layer, so one invalid
    item is marked NOK without failing the whole batch.
    """

    model_config = ConfigDict(
        title="Activity.BulkRequest",
    )

    activities: list[SkipValidation[ActivityRequest]] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Array of activity objects to process (1-1000 items per batch)",
    )


class ActivityBulkResultItem(BaseModel):
    """Result for a single item in a bulk activity response."""

    model_config = ConfigDict(
        title="Activity.BulkResultItem",
        populate_by_name=True,
    )

    activity_index: int = Field(
        ...,
        alias="activityIndex",
        ge=0,
        description="Zero-based index of this item in the original request list",
        examples=[0],
    )

    activity_id: str | None = Field(
        None,
        alias="activityId",
        description="Activity functional ID provided by the client in the request",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )

    status: Literal["OK", "NOK"] = Field(
        ...,
        description="Processing result - `OK` (created successfully) or `NOK` (failed validation or processing)",
        examples=["OK"],
    )

    activity: ActivityResponse | None = Field(
        None,
        description="The full activity object (present for OK items, omitted for NOK items)",
    )

    errors: ErrorResponse | None = Field(
        None,
        description="Structured error details (present for NOK items, omitted for OK items)",
        examples=[
            {
                "detail": [
                    {
                        "msg": "Area with areaId 'unknown-id' not found",
                        "type": "not_found_error",
                        "loc": ["areaId"],
                    }
                ]
            }
        ],
    )

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Exclude errors and activity from response when None."""
        data = serializer(self)
        if data.get("errors") is None:
            data.pop("errors", None)
        if data.get("activity") is None:
            data.pop("activity", None)
        return data


class ActivityBulkResponse(BaseModel):
    """Bulk activity response schema.

    Returns per-item OK/NOK feedback with summary counts.
    Validation flow Step 4: the original list enriched with status and error_message.
    """

    model_config = ConfigDict(
        title="Activity.BulkResponse",
        populate_by_name=True,
    )

    total_received: int = Field(
        ...,
        alias="totalReceived",
        ge=0,
        description="Total number of items received in the request",
        examples=[2],
    )

    succeeded: int = Field(
        ...,
        ge=0,
        description="Number of items successfully created (status OK)",
        examples=[2],
    )

    failed: int = Field(
        ...,
        ge=0,
        description="Number of items that failed validation or processing (status NOK)",
        examples=[0],
    )

    results: list[ActivityBulkResultItem] = Field(
        ...,
        description="Per-item results preserving the original request order",
        json_schema_extra={
            "example": [
                {
                    "activityIndex": 0,
                    "activityId": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "OK",
                    "activity": {
                        "activityId": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "finished",
                        "areaId": "3ab7c2b9-5c8d-4100-bc3e-00ac115f0495",
                        "competentAuthorityId": "sdep-ca0363",
                        "competentAuthorityName": "Gemeente Amsterdam",
                        "url": "http://example.com/amsterdam-myhouse-1",
                        "address": {
                            "thoroughfare": "Prinsengracht",
                            "locatorDesignatorNumber": 263,
                            "postCode": "1016GV",
                            "postName": "Amsterdam",
                            "fullAddress": "Prinsengracht 263, 1016GV Amsterdam",
                        },
                        "registrationNumber": "REG0001",
                        "numberOfGuests": 4,
                        "countryOfGuests": ["NLD", "DEU", "BEL", "N/A"],
                        "temporal": {
                            "startDatetime": "2025-06-01T14:00:00Z",
                            "endDatetime": "2025-06-07T11:00:00Z",
                        },
                        "platformId": "str01",
                        "platformName": "Test STR 01",
                        "createdAt": "2025-06-01T12:00:00Z",
                    },
                },
                {
                    "activityIndex": 1,
                    "status": "NOK",
                    "errors": {
                        "detail": [
                            {
                                "msg": "Area with areaId 'c5f54e98-226a-411b-b015-ca13070c6dc5' not found",
                                "type": "not_found_error",
                                "loc": ["areaId"],
                            }
                        ]
                    },
                },
            ]
        },
    )
