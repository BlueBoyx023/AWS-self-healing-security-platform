

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


    def test_concurrent_retry_claim_only_one_succeeds(self):
        event_id = "event-retry-concurrent-001"

        # Initial claim and simulated failure.
        self.assertTrue(self.store.claim_event(event_id))
        self.store.fail_event(event_id)

        # Explicitly authorize a retry.
        self.assertTrue(self.store.reset_event(event_id))

        # Ten workers attempt to claim the same retry.
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(
                executor.map(
                    self.store.claim_event,
                    [event_id] * 10,
                )
            )

        # Exactly one worker must succeed.
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 9)

        # The event must now be IN_PROGRESS.
        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.IN_PROGRESS,
        )

    def test_unclaimed_event_cannot_be_completed(self):
        with self.assertRaises(ValueError):
            self.store.complete_event("unclaimed-event-001")

        self.assertIsNone(
            self.store.get_status("unclaimed-event-001")
        )

    def test_unclaimed_event_cannot_be_failed(self):
        with self.assertRaises(ValueError):
            self.store.fail_event("unclaimed-event-002")

        self.assertIsNone(
            self.store.get_status("unclaimed-event-002")
        )

    def test_completed_event_cannot_be_reset(self):
        event_id = "completed-event-001"

        self.assertTrue(self.store.claim_event(event_id))
        self.store.complete_event(event_id)

        self.assertFalse(self.store.reset_event(event_id))

        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.COMPLETED,
        )

    def test_active_lease_cannot_be_recovered(self):
        event_id = "active-lease-001"

        owner_token = self.store.claim_event_with_lease(
            event_id,
            lease_seconds=10,
            now=100,
        )

        self.assertIsNotNone(owner_token)

        recovery_token = self.store.recover_stale_event(
            event_id,
            lease_seconds=10,
            now=105,
        )

        self.assertIsNone(recovery_token)

        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.IN_PROGRESS,
        )

    def test_expired_lease_can_be_recovered(self):
        event_id = "expired-lease-001"

        old_token = self.store.claim_event_with_lease(
            event_id,
            lease_seconds=10,
            now=100,
        )

        self.assertIsNotNone(old_token)

        new_token = self.store.recover_stale_event(
            event_id,
            lease_seconds=10,
            now=110,
        )

        self.assertIsNotNone(new_token)
        self.assertNotEqual(old_token, new_token)

        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.IN_PROGRESS,
        )

    def test_old_owner_cannot_complete_recovered_event(self):
        event_id = "stale-owner-001"

        old_token = self.store.claim_event_with_lease(
            event_id,
            lease_seconds=10,
            now=100,
        )

        new_token = self.store.recover_stale_event(
            event_id,
            lease_seconds=10,
            now=110,
        )

        self.assertIsNotNone(old_token)
        self.assertIsNotNone(new_token)

        with self.assertRaises(PermissionError):
            self.store.complete_event_owned(event_id, old_token)

        self.store.complete_event_owned(
    event_id,
    new_token,
    now=111,
)

        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.COMPLETED,
        )

    def test_expired_owner_cannot_fail_event(self):
        event_id = "expired-owner-001"

        owner_token = self.store.claim_event_with_lease(
            event_id,
            lease_seconds=10,
            now=100,
        )

        with self.assertRaises(PermissionError):
            self.store.fail_event_owned(
                event_id,
                owner_token,
                now=110,
            )

        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.IN_PROGRESS,
        )

    def test_valid_owner_can_fail_event(self):
        event_id = "valid-owner-001"

        owner_token = self.store.claim_event_with_lease(
            event_id,
            lease_seconds=10,
            now=100,
        )

        self.store.fail_event_owned(
            event_id,
            owner_token,
            now=105,
        )

        self.assertEqual(
            self.store.get_status(event_id),
            EventStatus.FAILED,
        )

    def test_concurrent_stale_recovery_only_one_owner(self):
        event_id = "concurrent-recovery-001"

        old_token = self.store.claim_event_with_lease(
            event_id,
            lease_seconds=10,
            now=100,
        )

        self.assertIsNotNone(old_token)

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(
                executor.map(
                    lambda _: self.store.recover_stale_event(
                        event_id,
                        lease_seconds=10,
                        now=110,
                    ),
                    range(10),
                )
            )

        successful_tokens = [
            token for token in results if token is not None
        ]

        self.assertEqual(len(successful_tokens), 1)
        self.assertEqual(len(results), 10)

        self.assertNotEqual(successful_tokens[0], old_token)

if __name__ == "__main__":
    unittest.main()
