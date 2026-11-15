

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Default audit log location
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "audit.jsonl"


def write_audit_record(
    event_id: str,
    event_type: str,
    resource_type: str,
    resource_id: str,
    action: str,
    status: str,
    verification_status: str | None = None,
    error: str | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """
    Create and persist a structured security audit record.

    Records are stored in JSON Lines format.
    Each record occupies one line.

    Audit failures are raised to the caller.
    They are never silently ignored.
    """

    # 1. Validate required fields
    required_fields = {
        "event_id": event_id,
        "event_type": event_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action": action,
        "status": status,
    }

    for field, value in required_fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Invalid audit field: {field}")

    # 2. Validate optional fields
    if verification_status is not None:
        if not isinstance(verification_status, str):
            raise ValueError("Invalid verification_status")

    if error is not None:
        if not isinstance(error, str):
            raise ValueError("Invalid error field")

    # 3. Generate UTC timestamp
    timestamp = datetime.now(timezone.utc).isoformat()

    # 4. Construct audit record
    record = {
        "timestamp": timestamp,
        "event_id": event_id,
        "event_type": event_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action": action,
        "status": status,
        "verification_status": verification_status,
        "error": error,
    }

    # 5. Determine log destination
    destination = Path(log_path) if log_path else DEFAULT_LOG_PATH

    # 6. Persist the audit record
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record) + "\n")
        log_file.flush()

    return record
