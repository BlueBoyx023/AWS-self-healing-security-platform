

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

from event_validator import validate_event


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


class TestEventValidator(unittest.TestCase):

    def test_valid_s3_event(self):
        event = create_valid_event()

        result = validate_event(event)

        self.assertEqual(
            result["bucket_name"],
            "test-security-bucket"
        )

    def test_invalid_event_source(self):
        event = create_valid_event()
        event["source"] = "untrusted.source"

        with self.assertRaises(ValueError):
            validate_event(event)

    def test_missing_bucket_identifier(self):
        event = create_valid_event()

        qualifier = (
            event["detail"]["newEvaluationResult"]
            ["evaluationResultIdentifier"]
            ["evaluationResultQualifier"]
        )

        del qualifier["resourceId"]

        with self.assertRaises(ValueError):
            validate_event(event)

    # Event ID validation tests

    def test_missing_event_id(self):
        event = create_valid_event()
        del event["id"]

        with self.assertRaises(ValueError):
            validate_event(event)

    def test_empty_event_id(self):
        event = create_valid_event()
        event["id"] = ""

        with self.assertRaises(ValueError):
            validate_event(event)

    def test_whitespace_event_id(self):
        event = create_valid_event()
        event["id"] = "   "

        with self.assertRaises(ValueError):
            validate_event(event)


if __name__ == "__main__":
    unittest.main()
