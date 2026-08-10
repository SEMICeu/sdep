"""Shared OpenAPI response examples for activity read endpoints."""

from typing import Any

from app.schemas.error import ErrorResponse

ACTIVITY_EXAMPLE_RESPONSE: dict[int | str, dict[str, Any]] = {
    "200": {
        "content": {
            "application/json": {
                "example": {
                    "activities": [
                        {
                            "activityId": "550e8400-e29b-41d4-a716-446655440000",
                            "activityName": "Amsterdam Summer Rental",
                            "status": "finished",
                            "areaId": "58ff0814-3aa1-5019-9afb-3cd9f398602c",
                            "areaName": "Amsterdam",
                            "competentAuthorityId": "c4ac8ccf-a281-5789-bad7-28dfac20ca7f",
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
                            "platformId": "8e70f1e2-4c61-477b-89b8-0dbf25ab8b21",
                            "platformName": "Test STR 01 (interactive usage, persistent)",
                            "createdAt": "2025-06-01T12:00:00Z",
                        }
                    ]
                }
            }
        }
    },
    "400": {
        "model": ErrorResponse,
        "description": "Bad request - invalid query parameters",
    },
    "401": {
        "model": ErrorResponse,
        "description": "Unauthorized - missing or invalid token",
    },
    "403": {
        "description": "Forbidden - insufficient permissions",
    },
}

COUNT_ACTIVITY_RESPONSES: dict[int | str, dict[str, Any]] = {
    "401": {
        "model": ErrorResponse,
        "description": "Unauthorized - missing or invalid token",
    },
    "403": {
        "description": "Forbidden - insufficient permissions",
    },
}

__all__ = ["ACTIVITY_EXAMPLE_RESPONSE", "COUNT_ACTIVITY_RESPONSES"]
