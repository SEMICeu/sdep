"""Validation exceptions."""

from .base import SDEPError


class ValidationError(SDEPError):
    """Raised when input validation fails.

    This is the base validation exception class. It is raised when:
    - Input data fails schema validation
    - File validation fails
    - Business rule validation fails
    - Data integrity validation fails
    """

    pass


class FileValidationError(ValidationError):
    """Raised when file validation fails.

    This exception is raised when:
    - File type is not supported
    - File size exceeds limits
    - File content is invalid or corrupt
    - File format is incorrect
    """

    pass


class DataValidationError(ValidationError):
    """Raised when data validation fails.

    This exception is raised when:
    - Data format is invalid
    - Required fields are missing
    - Field values are out of range
    - Data relationships are invalid
    - Data integrity constraints are violated
    """

    pass
