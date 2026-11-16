

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from time import monotonic
from uuid import uuid4


class EventStatus(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EventRecord:
    status: EventStatus
    claimed_at: float | None = None
    lease_expires_at: float | None = None
    owner_token: str | None = None


class IdempotencyStore:

    def __init__(self):
        self._events = {}
        self._lock = Lock()

    def claim_event(self, event_id: str) -> bool:
        """Claim an event using the legacy non-lease interface."""

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Event ID must be a non-empty string.")

        with self._lock:
            if event_id in self._events:
                return False

            self._events[event_id] = EventRecord(
                status=EventStatus.IN_PROGRESS
            )
            return True

    def claim_event_with_lease(
        self,
        event_id: str,
        lease_seconds: float = 60,
        now: float | None = None,
    ) -> str | None:
        """Claim an event and assign a time-limited ownership token."""

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Event ID must be a non-empty string.")

        if lease_seconds <= 0:
            raise ValueError("Lease duration must be positive.")

        current_time = monotonic() if now is None else now
        owner_token = uuid4().hex

        with self._lock:
            if event_id in self._events:
                return None

            self._events[event_id] = EventRecord(
                status=EventStatus.IN_PROGRESS,
                claimed_at=current_time,
                lease_expires_at=current_time + lease_seconds,
                owner_token=owner_token,
            )

            return owner_token

    def complete_event(self, event_id: str) -> None:
        """Complete an event using the legacy interface."""

        with self._lock:
            record = self._events.get(event_id)

            if record is None:
                raise ValueError("Event has not been claimed.")

            self._events[event_id] = EventRecord(
                status=EventStatus.COMPLETED,
                claimed_at=record.claimed_at,
                lease_expires_at=record.lease_expires_at,
                owner_token=record.owner_token,
            )


    def complete_event_owned(
        self,
        event_id: str,
        owner_token: str,
        now: float | None = None,
    ) -> None:
        """Complete an event only when the worker owns its active lease."""

        current_time = monotonic() if now is None else now

        with self._lock:
            record = self._events.get(event_id)

            if (
                record is None
                or record.status != EventStatus.IN_PROGRESS
                or record.owner_token != owner_token
                or record.lease_expires_at is None
                or current_time >= record.lease_expires_at
            ):
                raise PermissionError(
                    "Invalid or expired event ownership."
                )

            self._events[event_id] = EventRecord(
                status=EventStatus.COMPLETED,
                claimed_at=record.claimed_at,
                lease_expires_at=record.lease_expires_at,
                owner_token=record.owner_token,
            )


    def fail_event(self, event_id: str) -> None:
        """Mark an event as failed using the legacy interface."""

        with self._lock:
            record = self._events.get(event_id)

            if record is None:
                raise ValueError("Event has not been claimed.")

            self._events[event_id] = EventRecord(
                status=EventStatus.FAILED,
                claimed_at=record.claimed_at,
                lease_expires_at=record.lease_expires_at,
                owner_token=record.owner_token,
            )
    def fail_event_owned(
        self,
        event_id: str,
        owner_token: str,
        now: float | None = None,
    ) -> None:
        """Mark an event failed only when the worker owns its active lease."""

        current_time = monotonic() if now is None else now

        with self._lock:
            record = self._events.get(event_id)

            if (
                record is None
                or record.status != EventStatus.IN_PROGRESS
                or record.owner_token != owner_token
                or record.lease_expires_at is None
                or current_time >= record.lease_expires_at
            ):
                raise PermissionError(
                    "Invalid or expired event ownership."
                )

            self._events[event_id] = EventRecord(
                status=EventStatus.FAILED,
                claimed_at=record.claimed_at,
                lease_expires_at=record.lease_expires_at,
                owner_token=record.owner_token,
            )


    def recover_stale_event(
        self,
        event_id: str,
        lease_seconds: float = 60,
        now: float | None = None,
    ) -> str | None:
        """Atomically replace ownership of an expired event."""

        if lease_seconds <= 0:
            raise ValueError("Lease duration must be positive.")

        current_time = monotonic() if now is None else now

        with self._lock:
            record = self._events.get(event_id)

            if (
                record is None
                or record.status != EventStatus.IN_PROGRESS
                or record.lease_expires_at is None
                or current_time < record.lease_expires_at
            ):
                return None

            new_token = uuid4().hex

            self._events[event_id] = EventRecord(
                status=EventStatus.IN_PROGRESS,
                claimed_at=current_time,
                lease_expires_at=current_time + lease_seconds,
                owner_token=new_token,
            )

            return new_token

    def get_status(self, event_id: str):
        """Return the current processing status."""

        with self._lock:
            record = self._events.get(event_id)
            return record.status if record else None

    def reset_event(self, event_id: str) -> bool:
        """Remove a failed event to permit a new claim."""

        with self._lock:
            record = self._events.get(event_id)

            if record is None or record.status != EventStatus.FAILED:
                return False

            del self._events[event_id]
            return True
