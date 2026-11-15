

import unittest
from unittest.mock import Mock

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = PROJECT_ROOT / "lambda" / "remediation_engine"

sys.path.insert(0, str(METRICS_PATH))

from metrics import (
    NAMESPACE,
    METRIC_NAMES,
    publish_metric,
    record_security_event,
)


class TestMetrics(unittest.TestCase):

    def setUp(self):
        self.cloudwatch = Mock()

    def test_successful_metric_publication(self):
        result = publish_metric(
            self.cloudwatch,
            "RemediationSuccess",
            bucket_name="test-bucket",
        )

        self.assertTrue(result)
        self.cloudwatch.put_metric_data.assert_called_once()

    def test_correct_namespace(self):
        publish_metric(
            self.cloudwatch,
            "RemediationSuccess",
        )

        call = self.cloudwatch.put_metric_data.call_args.kwargs
        self.assertEqual(call["Namespace"], NAMESPACE)

    def test_unsupported_metric_rejected(self):
        with self.assertRaises(ValueError):
            publish_metric(
                self.cloudwatch,
                "InvalidMetric",
            )

    def test_negative_metric_rejected(self):
        with self.assertRaises(ValueError):
            publish_metric(
                self.cloudwatch,
                "RemediationSuccess",
                value=-1,
            )

    def test_invalid_metric_value_rejected(self):
        with self.assertRaises(ValueError):
            publish_metric(
                self.cloudwatch,
                "RemediationSuccess",
                value="invalid",
            )

    def test_missing_bucket_name_rejected(self):
        with self.assertRaises(ValueError):
            publish_metric(
                self.cloudwatch,
                "RemediationSuccess",
                bucket_name="",
            )

    def test_missing_environment_rejected(self):
        with self.assertRaises(ValueError):
            publish_metric(
                self.cloudwatch,
                "RemediationSuccess",
                environment="",
            )

    def test_cloudwatch_failure_handled(self):
        self.cloudwatch.put_metric_data.side_effect = Exception(
            "CloudWatch unavailable"
        )

        result = publish_metric(
            self.cloudwatch,
            "RemediationFailure",
        )

        self.assertFalse(result)

    def test_missing_cloudwatch_client(self):
        result = publish_metric(
            None,
            "RemediationSuccess",
        )

        self.assertFalse(result)

    def test_successful_security_event(self):
        result = record_security_event(
            self.cloudwatch,
            "success",
        )

        self.assertTrue(result)

    def test_all_event_types_supported(self):
        for event_type in METRIC_NAMES:
            with self.subTest(event_type=event_type):
                self.cloudwatch.reset_mock()

                result = record_security_event(
                    self.cloudwatch,
                    event_type,
                )

                self.assertTrue(result)

    def test_invalid_security_event_rejected(self):
        with self.assertRaises(ValueError):
            record_security_event(
                self.cloudwatch,
                "unknown_event",
            )


if __name__ == "__main__":
    unittest.main()
