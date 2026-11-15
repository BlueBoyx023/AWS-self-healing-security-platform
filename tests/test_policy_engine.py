

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

from policy_engine import is_remediation_allowed


class TestPolicyEngine(unittest.TestCase):

    def setUp(self):
        self.allowed_buckets = {
            "test-security-bucket"
        }

    # Approved bucket
    def test_approved_bucket(self):
        result = is_remediation_allowed(
            "AWS::S3::Bucket",
            "test-security-bucket",
            self.allowed_buckets
        )

        self.assertTrue(result)

    # T04: Unauthorized bucket
    def test_unauthorized_bucket(self):
        result = is_remediation_allowed(
            "AWS::S3::Bucket",
            "unknown-bucket",
            self.allowed_buckets
        )

        self.assertFalse(result)

    # Unsupported AWS resource
    def test_unsupported_resource(self):
        result = is_remediation_allowed(
            "AWS::EC2::Instance",
            "test-security-bucket",
            self.allowed_buckets
        )

        self.assertFalse(result)

    # Missing bucket identifier
    def test_missing_bucket_identifier(self):
        result = is_remediation_allowed(
            "AWS::S3::Bucket",
            "",
            self.allowed_buckets
        )

        self.assertFalse(result)

    # Invalid allowlist
    def test_invalid_allowlist(self):
        result = is_remediation_allowed(
            "AWS::S3::Bucket",
            "test-security-bucket",
            ["test-security-bucket"]
        )

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
