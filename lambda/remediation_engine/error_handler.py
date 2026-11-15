

"""
Centralized error handling for the AWS Self-Healing Security Platform.

Provides structured error responses, safe error classification,
and consistent handling of AWS API failures.
"""

from datetime import datetime, timezone
from typing import Any


class RemediationError(Exception):
    """Base exception for remediation platform errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "REMEDIATION_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ValidationError(RemediationError):
    """Raised when an event or resource fails validation."""

    def __init__(self, message: str, details=None):
        super().__init__(message, "VALIDATION_ERROR", details)


class AuthorizationError(RemediationError):
    """Raised when a resource is not authorized for remediation."""

    def __init__(self, message: str, details=None):
        super().__init__(message, "AUTHORIZATION_ERROR", details)


class RemediationExecutionError(RemediationError):
    """Raised when an automated remediation operation fails."""

    def __init__(self, message: str, details=None):
        super().__init__(message, "REMEDIATION_EXECUTION_ERROR", details)


class VerificationError(RemediationError):
    """Raised when post-remediation verification fails."""

    def __init__(self, message: str, details=None):
        super().__init__(message, "VERIFICATION_ERROR", details)


def handle_error(error: Exception) -> dict[str, Any]:
    """
    Convert an exception into a standardized error response.

    Does not expose stack traces or internal system details.
    """

    if isinstance(error, RemediationError):
        error_code = error.error_code
        message = error.message
        details = error.details
    else:
        error_code = "INTERNAL_ERROR"
        message = "An unexpected internal error occurred."
        details = {}

    return {
        "status": "ERROR",
        "error_code": error_code,
        "message": message,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
