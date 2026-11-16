

import unittest
from unittest.mock import patch

import orchestrator


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        # Give every test an independent idempotency store.
        self.idempotency_store = orchestrator.IdempotencyStore()

        self.event = {
            "id": "test-event-001"
        }

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
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(result["status"], "REJECTED")

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    def test_unauthorized_bucket_denied(
        self,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = False

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(result["status"], "DENIED")
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.COMPLETED,
        )

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    def test_dry_run_execution(
        self,
        mock_remediate,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True
        mock_remediate.return_value = {"status": "SUCCESS"}

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=True,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(result["status"], "SIMULATED")
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.COMPLETED,
        )

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    def test_remediation_failure(
        self,
        mock_remediate,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True
        mock_remediate.return_value = {"status": "FAILED"}

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.FAILED,
        )

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    @patch("orchestrator.verify_s3_bucket")
    def test_verification_failure(
        self,
        mock_verify,
        mock_remediate,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True
        mock_remediate.return_value = {"status": "SUCCESS"}
        mock_verify.return_value = {"status": "UNVERIFIED"}

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.FAILED,
        )

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    @patch("orchestrator.verify_s3_bucket")
    def test_successful_workflow(
        self,
        mock_verify,
        mock_remediate,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True
        mock_remediate.return_value = {"status": "SUCCESS"}
        mock_verify.return_value = {"status": "VERIFIED"}

        result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.COMPLETED,
        )

    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    @patch("orchestrator.verify_s3_bucket")
    def test_duplicate_event_does_not_remediate_twice(
        self,
        mock_verify,
        mock_remediate,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True
        mock_remediate.return_value = {"status": "SUCCESS"}
        mock_verify.return_value = {"status": "VERIFIED"}

        first_result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        second_result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(first_result["status"], "VERIFIED")
        self.assertEqual(second_result["status"], "DUPLICATE")
        mock_remediate.assert_called_once()


    @patch("orchestrator.validate_event")
    @patch("orchestrator.is_remediation_allowed")
    @patch("orchestrator.remediate_s3_bucket")
    @patch("orchestrator.verify_s3_bucket")
    def test_failed_event_can_be_retried_successfully(
        self,
        mock_verify,
        mock_remediate,
        mock_policy,
        mock_validate,
    ):
        mock_validate.return_value = self.validated_event
        mock_policy.return_value = True
        mock_remediate.side_effect = [
            {"status": "FAILED"},
            {"status": "SUCCESS"},
        ]
        mock_verify.return_value = {"status": "VERIFIED"}

        # First attempt: remediation fails.
        first_result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(first_result["status"], "FAILED")
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.FAILED,
        )

        # Explicitly authorize retry of the failed event.
        reset_result = self.idempotency_store.reset_event("test-event-001")
        self.assertTrue(reset_result)

        # Second attempt: remediation succeeds.
        second_result = orchestrator.process_security_event(
            self.event,
            self.allowed_buckets,
            self.s3_client,
            dry_run=False,
            idempotency_store=self.idempotency_store,
        )

        self.assertEqual(second_result["status"], "VERIFIED")
        self.assertEqual(mock_remediate.call_count, 2)
        self.assertEqual(
            self.idempotency_store.get_status("test-event-001"),
            orchestrator.EventStatus.COMPLETED,
        )

if __name__ == "__main__":
    unittest.main()
