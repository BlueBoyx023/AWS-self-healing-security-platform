

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "lambda"
        / "remediation_engine"
    ),
)

import orchestrator


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.event = {"id": "test-event-001"}

        self.validated_event = {
            "event_id": "test-event-001",
            "bucket_name": "approved-test-bucket",
            "resource_type": "AWS::S3::Bucket",
            "region": "ap-south-1",
            "compliance_status": "NON_COMPLIANT",
            "rule_name": "s3-public-access-check",
        }

        self.allowed_buckets = {"approved-test-bucket"}
        self.s3_client = object()

    @patch("orchestrator.validate_event")
    def test_invalid_event_rejected(self, mock_validate):
        mock_validate.side_effect = ValueError("Invalid event")

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
        )

        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["stage"], "VALIDATION")

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    def test_unauthorized_bucket_denied(
        self, mock_policy, mock_validate
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = False

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
        )

        self.assertEqual(result["status"], "DENIED")
        self.assertEqual(result["stage"], "POLICY")

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    def test_dry_run_execution(
        self, mock_remediate, mock_policy, mock_validate
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True

        mock_remediate.return_value = {
            "status": "DRY_RUN",
            "bucket_name": "approved-test-bucket",
        }

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=True,
        )

        self.assertEqual(result["status"], "SIMULATED")
        self.assertEqual(result["verification"], "SKIPPED")

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    def test_remediation_failure(
        self, mock_remediate, mock_policy, mock_validate
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True

        mock_remediate.return_value = {
            "status": "FAILED",
            "message": "AWS API error",
        }

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["stage"], "REMEDIATION")

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    @patch("orchestrator.verify_s3_bucket")
    def test_verification_failure(
        self, mock_verify, mock_remediate,
        mock_policy, mock_validate
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True

        mock_remediate.return_value = {"status": "SUCCESS"}

        mock_verify.return_value = {
            "status": "UNVERIFIED",
            "message": "Security settings do not match",
        }

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
        )

        self.assertEqual(result["status"], "UNVERIFIED")

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    @patch("orchestrator.verify_s3_bucket")
    def test_successful_workflow(
        self, mock_verify, mock_remediate,
        mock_policy, mock_validate
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True

        mock_remediate.return_value = {
            "status": "SUCCESS"
        }

        mock_verify.return_value = {
            "status": "VERIFIED"
        }

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
        )

        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(
            result["verification"]["status"], "VERIFIED"
        )


if __name__ == "__main__":
    unittest.main()
