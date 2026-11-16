

"""
AWS Self-Healing Security Platform
Local Idempotency Engine

Prevents duplicate security events from triggering
repeated remediation during local development.
"""

from enum import Enum
from threading import Lock


class EventStatus(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdempotencyStore:

    def __init__(self):
        self._events = {}
        self._lock = Lock()

    def claim_event(self, event_id: str) -> bool:
        """Atomically claim a new event for processing."""

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Event ID must be a non-empty string.")

        with self._lock:
            if event_id in self._events:
                return False

            self._events[event_id] = EventStatus.IN_PROGRESS
            return True

    def complete_event(self, event_id: str) -> None:
        """Mark an event as successfully completed."""

        with self._lock:
            if event_id not in self._events:
                raise ValueError("Event has not been claimed.")

            self._events[event_id] = EventStatus.COMPLETED

    def fail_event(self, event_id: str) -> None:
        """Mark an event as failed and eligible for retry."""

        with self._lock:
            if event_id not in self._events:
                raise ValueError("Event has not been claimed.")

            self._events[event_id] = EventStatus.FAILED

    def get_status(self, event_id: str):
        """Return the current processing status."""

        with self._lock:
            return self._events.get(event_id)

    def reset_event(self, event_id: str) -> bool:
        """Remove a failed event to permit a new claim."""

        with self._lock:
            if self._events.get(event_id) != EventStatus.FAILED:
                return False

            del self._events[event_id]
            return True
