

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

import orchestrator


def create_valid_event():
    return {
        "id": "test-event-001",
        "source": "aws.config",
        "detail-type": "Config Rules Compliance Change",
        "region": "ap-south-1",
        "detail": {
            "configRuleName": "s3-bucket-public-read-prohibited",
            "newEvaluationResult": {
                "complianceType": "NON_COMPLIANT",
                "evaluationResultIdentifier": {
                    "evaluationResultQualifier": {
                        "resourceType": "AWS::S3::Bucket",
                        "resourceId": "test-security-bucket"
                    }
                }
            }
        }
    }


class TestOrchestratorMetrics(unittest.TestCase):

    def setUp(self):
        self.event = create_valid_event()
        self.bucket = "test-security-bucket"
        self.allowed_buckets = {self.bucket}
        self.s3_client = Mock()
        self.cloudwatch_client = Mock()

        self.audit_patcher = patch.object(
            orchestrator,
            "write_audit_record",
            return_value={}
        )
        self.mock_audit = self.audit_patcher.start()

        self.metrics_patcher = patch.object(
            orchestrator,
            "record_security_event",
            return_value=True
        )
        self.mock_metrics = self.metrics_patcher.start()

    def tearDown(self):
        self.audit_patcher.stop()
        self.metrics_patcher.stop()

    def test_successful_workflow_audit_logging(self):
        with patch.object(
            orchestrator,
            "remediate_s3_bucket",
            return_value={"status": "SUCCESS"}
        ), patch.object(
            orchestrator,
            "verify_s3_bucket",
            return_value={"status": "VERIFIED"}
        ):
            result = orchestrator.process_security_event(
                event=self.event,
                allowed_buckets=self.allowed_buckets,
                s3_client=self.s3_client,
                dry_run=False,
                cloudwatch_client=self.cloudwatch_client
            )

        self.assertEqual(result["status"], "VERIFIED")

        self.mock_audit.assert_called_once()
        audit_record = self.mock_audit.call_args.kwargs

        self.assertEqual(audit_record["status"], "VERIFIED")
        self.assertEqual(audit_record["event_id"], "test-event-001")

        self.mock_metrics.assert_called_once()
        self.assertEqual(
            self.mock_metrics.call_args.kwargs["event_type"],
            "success"
        )

    def test_unauthorized_attempt_logging(self):
        with patch.object(
            orchestrator,
            "is_remediation_allowed",
            return_value=False
        ):
            result = orchestrator.process_security_event(
                event=self.event,
                allowed_buckets=set(),
                s3_client=self.s3_client,
                cloudwatch_client=self.cloudwatch_client
            )

        self.assertEqual(result["status"], "DENIED")

        audit_record = self.mock_audit.call_args.kwargs
        self.assertEqual(audit_record["status"], "DENIED")
        self.assertEqual(
            audit_record["error"],
            "Resource not authorized"
        )

        self.assertEqual(
            self.mock_metrics.call_args.kwargs["event_type"],
            "unauthorized"
        )

    def test_dry_run_audit_logging(self):
        with patch.object(
            orchestrator,
            "remediate_s3_bucket",
            return_value={"status": "DRY_RUN"}
        ):
            result = orchestrator.process_security_event(
                event=self.event,
                allowed_buckets=self.allowed_buckets,
                s3_client=self.s3_client,
                dry_run=True,
                cloudwatch_client=self.cloudwatch_client
            )

        self.assertEqual(result["status"], "SIMULATED")
        self.assertEqual(result["verification"], "SKIPPED")

        audit_record = self.mock_audit.call_args.kwargs
        self.assertEqual(audit_record["status"], "DRY_RUN")
        self.assertEqual(
            audit_record["verification_status"],
            "SKIPPED"
        )

        self.assertEqual(
            self.mock_metrics.call_args.kwargs["event_type"],
            "dry_run"
        )

    def test_verification_failure_logging(self):
        with patch.object(
            orchestrator,
            "remediate_s3_bucket",
            return_value={"status": "SUCCESS"}
        ), patch.object(
            orchestrator,
            "verify_s3_bucket",
            side_effect=Exception("Verification failed")
        ):
            result = orchestrator.process_security_event(
                event=self.event,
                allowed_buckets=self.allowed_buckets,
                s3_client=self.s3_client,
                dry_run=False,
                cloudwatch_client=self.cloudwatch_client
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["stage"], "VERIFICATION")

        audit_record = self.mock_audit.call_args.kwargs
        self.assertEqual(audit_record["status"], "FAILED")
        self.assertEqual(
            audit_record["verification_status"],
            "UNVERIFIED"
        )

        self.assertEqual(
            self.mock_metrics.call_args.kwargs["event_type"],
            "verification_failure"
        )

    def test_cloudwatch_failure_handling(self):
        self.mock_metrics.side_effect = Exception(
            "CloudWatch unavailable"
        )

        with patch.object(
            orchestrator,
            "remediate_s3_bucket",
            return_value={"status": "SUCCESS"}
        ), patch.object(
            orchestrator,
            "verify_s3_bucket",
            return_value={"status": "VERIFIED"}
        ):
            result = orchestrator.process_security_event(
                event=self.event,
                allowed_buckets=self.allowed_buckets,
                s3_client=self.s3_client,
                dry_run=False,
                cloudwatch_client=self.cloudwatch_client
            )

        self.assertEqual(result["status"], "VERIFIED")
        self.mock_audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
