from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from packages.schemas.control_plane import ControlPlaneActionState
from packages.schemas.control_plane_ledger import (
    CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION,
    ZERO_AUDIT_HASH,
    ControlPlaneAuditEvent,
    ControlPlaneAuditEventType,
)


class ControlPlaneAuditLogError(RuntimeError):
    pass


def _hash_payload(
    *,
    sequence: int,
    event_id: str,
    event_type: ControlPlaneAuditEventType,
    occurred_at_utc: datetime,
    actor: str,
    action_id: str | None,
    action_fingerprint: str | None,
    action_state: ControlPlaneActionState | None,
    details: dict[str, Any],
    previous_event_hash: str,
) -> str:
    payload = {
        "contract_version": CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION,
        "sequence": sequence,
        "event_id": event_id,
        "event_type": event_type.value,
        "occurred_at_utc": occurred_at_utc.isoformat(),
        "actor": actor,
        "action_id": action_id,
        "action_fingerprint": action_fingerprint,
        "action_state": action_state.value if action_state is not None else None,
        "details": details,
        "previous_event_hash": previous_event_hash,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ControlPlaneAuditLog:
    """Small local append-only JSONL ledger with a verified SHA-256 hash chain."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()

    def read_verified(self) -> tuple[ControlPlaneAuditEvent, ...]:
        if not self.path.exists():
            return ()
        if not self.path.is_file():
            raise ControlPlaneAuditLogError(f"audit log path is not a file: {self.path}")
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ControlPlaneAuditLogError("audit log is unreadable") from exc
        events: list[ControlPlaneAuditEvent] = []
        previous = ZERO_AUDIT_HASH
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                raise ControlPlaneAuditLogError(f"audit log contains blank line at sequence {index}")
            try:
                raw = json.loads(line)
                event = ControlPlaneAuditEvent.model_validate(raw)
            except Exception as exc:
                raise ControlPlaneAuditLogError(f"invalid audit event at sequence {index}") from exc
            if event.sequence != index:
                raise ControlPlaneAuditLogError("audit event sequence is not contiguous")
            if event.previous_event_hash != previous:
                raise ControlPlaneAuditLogError("audit event previous hash does not match chain")
            previous = event.event_hash
            events.append(event)
        return tuple(events)

    def append(
        self,
        *,
        event_type: ControlPlaneAuditEventType,
        actor: str,
        action_id: str | None = None,
        action_fingerprint: str | None = None,
        action_state: ControlPlaneActionState | None = None,
        details: dict[str, Any] | None = None,
    ) -> ControlPlaneAuditEvent:
        if actor not in {"local_user", "atlas_system"}:
            raise ControlPlaneAuditLogError("unsupported audit actor")
        with self._lock:
            events = self.read_verified()
            sequence = len(events) + 1
            previous = events[-1].event_hash if events else ZERO_AUDIT_HASH
            occurred = self._clock()
            if occurred.tzinfo is None:
                raise ControlPlaneAuditLogError("audit clock must return timezone-aware datetime")
            occurred = occurred.astimezone(UTC)
            event_id = uuid.uuid4().hex
            event_details = dict(details or {})
            event_hash = _hash_payload(
                sequence=sequence,
                event_id=event_id,
                event_type=event_type,
                occurred_at_utc=occurred,
                actor=actor,
                action_id=action_id,
                action_fingerprint=action_fingerprint,
                action_state=action_state,
                details=event_details,
                previous_event_hash=previous,
            )
            event = ControlPlaneAuditEvent(
                sequence=sequence,
                event_id=event_id,
                event_type=event_type,
                occurred_at_utc=occurred,
                actor=actor,
                action_id=action_id,
                action_fingerprint=action_fingerprint,
                action_state=action_state,
                details=event_details,
                previous_event_hash=previous,
                event_hash=event_hash,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = (event.model_dump_json() + "\n").encode("utf-8")
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            fd = os.open(self.path, flags, 0o600)
            try:
                written = os.write(fd, line)
                if written != len(line):
                    raise ControlPlaneAuditLogError("short write while appending audit event")
                os.fsync(fd)
            finally:
                os.close(fd)
            return event
