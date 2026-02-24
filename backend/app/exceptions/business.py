"""Business logic exceptions."""

from .base import SDEPError


class ApplicationValidationError(SDEPError):
    """Raised when business logic validation fails."""

    pass


class ResourceNotFoundError(SDEPError):
    """Raised when a requested resource cannot be found."""

    pass


class DuplicateResourceError(ApplicationValidationError):
    """Raised when attempting to create a duplicate resource."""

    pass


class InvalidOperationError(ApplicationValidationError):
    """Raised when an operation is not valid in the current context.

    This exception is raised when:
    - Operation is not allowed in current state
    - User does not have required permissions
    - Operation would violate business rules
    - Operation would create invalid data state
    - Required preconditions are not met
    """

    pass
