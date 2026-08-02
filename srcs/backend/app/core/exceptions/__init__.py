class UnauthorizedException(Exception):
    """Raised when authentication fails or access is unauthorized."""


class InvalidCredentialsError(UnauthorizedException):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__("Incorrect email or password")

class NotImplementException(Exception):
    """Raised for API surfaces that are intentionally not implemented yet."""

class NotFoundException(Exception):
    """Raised when a requested resource is not found."""

class AlreadyExistsException(Exception):
    """Raised when a resource with a unique constraint already exists."""

class ConflictException(Exception):
    """Raised when a conflict occurs (e.g., optimistic concurrency conflict)."""


class StateConflictException(Exception):
    """Raised when a resource is in a conflicting state."""


class ValidationException(Exception):
    """Raised when a request cannot be processed because its input is invalid."""


class BadGatewayException(Exception):
    """Raised when an upstream dependency returns an invalid response."""


class ServiceUnavailableException(Exception):
    """Raised when a required dependency is temporarily unavailable."""


class GatewayTimeoutException(Exception):
    """Raised when an upstream dependency does not respond in time."""
