

import sys
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMEDIATION_PATH = (
    PROJECT_ROOT / "lambda" / "remediation_engine"
)

sys.path.insert(0, str(REMEDIATION_PATH))

from idempotency import IdempotencyStore, EventStatus


class TestIdempotency(unittest.TestCase):

    def setUp(self):
        self.store = IdempotencyStore()

    def test_first_event_accepted(self):
        result = self.store.claim_event("event-001")

        self.assertTrue(result)
        self.assertEqual(
            self.store.get_status("event-001"),
            EventStatus.IN_PROGRESS
        )

    def test_duplicate_event_rejected(self):
        self.store.claim_event("event-001")

        result = self.store.claim_event("event-001")

        self.assertFalse(result)

    def test_completed_event_rejected(self):
        self.store.claim_event("event-001")
        self.store.complete_event("event-001")

        result = self.store.claim_event("event-001")

        self.assertFalse(result)
        self.assertEqual(
            self.store.get_status("event-001"),
            EventStatus.COMPLETED
        )

    def test_failed_event_can_be_retried(self):
        self.store.claim_event("event-001")
        self.store.fail_event("event-001")

        self.assertEqual(
            self.store.get_status("event-001"),
            EventStatus.FAILED
        )

        self.assertTrue(
            self.store.reset_event("event-001")
        )

        self.assertTrue(
            self.store.claim_event("event-001")
        )

    def test_different_event_ids_accepted(self):
        first = self.store.claim_event("event-001")
        second = self.store.claim_event("event-002")

        self.assertTrue(first)
        self.assertTrue(second)

    def test_missing_event_id_rejected(self):
        invalid_ids = ["", "   ", None, 123]

        for event_id in invalid_ids:
            with self.subTest(event_id=event_id):
                with self.assertRaises(ValueError):
                    self.store.claim_event(event_id)

    def test_concurrent_duplicate_claim(self):
        event_id = "event-concurrent-001"

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(
                executor.map(
                    self.store.claim_event,
                    [event_id] * 10
                )
            )

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 9)


if __name__ == "__main__":
    unittest.main()
