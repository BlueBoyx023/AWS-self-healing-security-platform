

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

import sys

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "lambda"
        / "remediation_engine"
    ),
)

from audit_logger import write_audit_record


class TestAuditLogger(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.temp_dir.name) / "audit.jsonl"

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_record(self, **overrides):
        data = {
            "event_id": "event-001",
            "event_type": "SECURITY_FINDING",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": "test-bucket",
            "action": "BLOCK_PUBLIC_ACCESS",
            "status": "SUCCESS",
            "verification_status": "VERIFIED",
        }

        data.update(overrides)
        return write_audit_record(
            **data,
            log_path=self.log_path,
        )

    def test_successful_audit_record(self):
        record = self.create_record()

        self.assertEqual(record["status"], "SUCCESS")
        self.assertEqual(record["event_id"], "event-001")

    def test_timestamp_is_valid_utc(self):
        record = self.create_record()

        timestamp = datetime.fromisoformat(
            record["timestamp"]
        )

        self.assertEqual(timestamp.utcoffset().total_seconds(), 0)

    def test_audit_file_created(self):
        self.create_record()

        self.assertTrue(self.log_path.exists())

    def test_record_is_valid_json(self):
        self.create_record()

        with self.log_path.open(encoding="utf-8") as file:
            record = json.loads(file.readline())

        self.assertEqual(record["resource_id"], "test-bucket")

    def test_multiple_records_are_appended(self):
        self.create_record(event_id="event-001")
        self.create_record(event_id="event-002")

        with self.log_path.open(encoding="utf-8") as file:
            records = [json.loads(line) for line in file]

        self.assertEqual(len(records), 2)

    def test_missing_event_id_rejected(self):
        with self.assertRaises(ValueError):
            self.create_record(event_id="")

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):
            self.create_record(status="")

    def test_error_details_recorded(self):
        record = self.create_record(
            status="FAILED",
            error="AWS API failure",
        )

        self.assertEqual(record["error"], "AWS API failure")


if __name__ == "__main__":
    unittest.main()
