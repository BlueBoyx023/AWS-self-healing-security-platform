

import unittest
import sys
from pathlib import Path
from datetime import datetime

# Configure project import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

from error_handler import (
    RemediationError,
    ValidationError,
    AuthorizationError,
    RemediationExecutionError,
    VerificationError,
    handle_error,
)


class TestErrorHandler(unittest.TestCase):

    def test_custom_error_handling(self):
        error = RemediationError("Test failure")
        result = handle_error(error)

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(
            result["error_code"],
            "REMEDIATION_ERROR"
        )

    def test_validation_error(self):
        error = ValidationError("Invalid event")
        result = handle_error(error)

        self.assertEqual(
            result["error_code"],
            "VALIDATION_ERROR"
        )

    def test_authorization_error(self):
        error = AuthorizationError("Unauthorized bucket")
        result = handle_error(error)

        self.assertEqual(
            result["error_code"],
            "AUTHORIZATION_ERROR"
        )

    def test_remediation_execution_error(self):
        error = RemediationExecutionError("S3 API failure")
        result = handle_error(error)

        self.assertEqual(
            result["error_code"],
            "REMEDIATION_EXECUTION_ERROR"
        )

    def test_verification_error(self):
        error = VerificationError("Verification failed")
        result = handle_error(error)

        self.assertEqual(
            result["error_code"],
            "VERIFICATION_ERROR"
        )

    def test_unexpected_internal_error(self):
        error = RuntimeError("Sensitive internal information")
        result = handle_error(error)

        self.assertEqual(
            result["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertEqual(
            result["message"],
            "An unexpected internal error occurred."
        )

        self.assertNotIn(
            "Sensitive internal information",
            result["message"]
        )

    def test_error_details_preserved(self):
        details = {
            "bucket_name": "test-bucket"
        }

        error = ValidationError(
            "Invalid bucket",
            details=details
        )

        result = handle_error(error)

        self.assertEqual(
            result["details"],
            details
        )

    def test_timestamp_is_valid(self):
        error = ValidationError("Test")
        result = handle_error(error)

        timestamp = datetime.fromisoformat(
            result["timestamp"]
        )

        self.assertIsNotNone(timestamp.tzinfo)


if __name__ == "__main__":
    unittest.main()
