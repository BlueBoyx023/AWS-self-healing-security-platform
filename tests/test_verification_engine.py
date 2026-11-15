

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

from verification_engine import verify_s3_bucket


class TestVerificationEngine(unittest.TestCase):

    def setUp(self):
        self.s3_client = Mock()
        self.bucket_name = "test-security-bucket"

    def valid_response(self):
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True
            }
        }

    # V01: All security settings enabled
    def test_successful_verification(self):
        self.s3_client.get_public_access_block.return_value = (
            self.valid_response()
        )

        result = verify_s3_bucket(
            self.bucket_name,
            self.s3_client
        )

        self.assertEqual(result["status"], "VERIFIED")

    # V02: One security setting disabled
    def test_incorrect_security_settings(self):
        response = self.valid_response()
        response["PublicAccessBlockConfiguration"][
            "BlockPublicAcls"
        ] = False

        self.s3_client.get_public_access_block.return_value = response

        result = verify_s3_bucket(
            self.bucket_name,
            self.s3_client
        )

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIn("BlockPublicAcls", result["failed_settings"])

    # V03: Missing configuration
    def test_missing_configuration(self):
        self.s3_client.get_public_access_block.return_value = {}

        result = verify_s3_bucket(
            self.bucket_name,
            self.s3_client
        )

        self.assertEqual(result["status"], "UNVERIFIED")

    # V04: Invalid bucket name
    def test_invalid_bucket_name(self):
        with self.assertRaises(ValueError):
            verify_s3_bucket("", self.s3_client)

    # V05: AWS API failure
    def test_aws_api_failure(self):
        self.s3_client.get_public_access_block.side_effect = (
            RuntimeError("Simulated AWS API failure")
        )

        result = verify_s3_bucket(
            self.bucket_name,
            self.s3_client
        )

        self.assertEqual(result["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
