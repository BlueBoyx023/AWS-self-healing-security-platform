

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

from remediation_engine import remediate_s3_bucket


class TestRemediationEngine(unittest.TestCase):

    def setUp(self):
        self.s3_client = Mock()
        self.bucket_name = "test-security-bucket"

    # T05: Dry-run must not modify AWS
    def test_dry_run(self):
        result = remediate_s3_bucket(
            self.bucket_name,
            self.s3_client,
            dry_run=True
        )

        self.assertEqual(result["status"], "DRY_RUN")
        self.s3_client.put_public_access_block.assert_not_called()

    # Successful remediation API call
    def test_successful_remediation(self):
        result = remediate_s3_bucket(
            self.bucket_name,
            self.s3_client,
            dry_run=False
        )

        self.assertEqual(result["status"], "SUCCESS")

        self.s3_client.put_public_access_block.assert_called_once()

    # Invalid bucket name
    def test_invalid_bucket_name(self):
        with self.assertRaises(ValueError):
            remediate_s3_bucket(
                "",
                self.s3_client,
                dry_run=False
            )

    # Missing S3 client
    def test_missing_s3_client(self):
        with self.assertRaises(ValueError):
            remediate_s3_bucket(
                self.bucket_name,
                None,
                dry_run=False
            )

    # AWS API failure
    def test_aws_api_failure(self):
        self.s3_client.put_public_access_block.side_effect = (
            RuntimeError("Simulated AWS API failure")
        )

        result = remediate_s3_bucket(
            self.bucket_name,
            self.s3_client,
            dry_run=False
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("Simulated AWS API failure", result["message"])


if __name__ == "__main__":
    unittest.main()
