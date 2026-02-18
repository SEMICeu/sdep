"""Base exception classes for the SDEP application."""

from typing import Any


class SDEPError(Exception):
    """Base exception class for all SDEP application exceptions."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message='{self.message}', details={self.details})"
