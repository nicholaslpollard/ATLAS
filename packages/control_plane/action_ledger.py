from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Callable

from packages.core.settings import AtlasSettings
from packages.schemas.control_plane import (
    ControlPlaneActionRequest,
    ControlPlaneActionState,
    ControlPlaneConfirmationGrant,
    confirmation_matches_request,
    required_confirmation_scope,
)
from packages.schemas.control_plane_ledger import (
    ControlPlaneActionRecord,
    ControlPlaneAuditEventType,
)

from .audit_log import ControlPlaneAuditLog, ControlPlaneAuditLogError


class ControlPlaneActionLedgerError(RuntimeError):
    pass


class ControlPlaneActionConflict(ControlPlaneActionLedgerError):
    pass


class ControlPlaneActionNotFound(ControlPlaneActionLedgerError):
    pass


class ControlPlaneActionLedger:
    """Audit-log-backed action state machine; no broker methods are called here."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "control_plane" / "v1"
        self.audit_log = ControlPlaneAuditLog(
            self.root / "audit" / "actions.jsonl", clock=self._clock
        )
        self._lock = threading.RLock()

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ControlPlaneActionLedgerError("action clock must be timezone-aware")
        return value.astimezone(UTC)

    def records(self) -> dict[str, ControlPlaneActionRecord]:
        try:
            events = self.audit_log.read_verified()
        except ControlPlaneAuditLogError as exc:
            raise ControlPlaneActionLedgerError("action audit chain failed verification") from exc
        latest: dict[str, ControlPlaneActionRecord] = {}
        idempotency_owner: dict[str, str] = {}
        for event in events:
            raw_record = event.details.get("record")
            if raw_record is None:
                continue
            try:
                record = ControlPlaneActionRecord.model_validate(raw_record)
            except Exception as exc:
                raise ControlPlaneActionLedgerError(
                    f"invalid action record snapshot in audit sequence {event.sequence}"
                ) from exc
            action_id = record.request.action_id
            if event.action_id != action_id:
                raise ControlPlaneActionLedgerError("audit action id differs from record snapshot")
            if event.action_fingerprint != record.request_fingerprint:
                raise ControlPlaneActionLedgerError(
                    "audit action fingerprint differs from record snapshot"
                )
            if event.action_state != record.state:
                raise ControlPlaneActionLedgerError("audit action state differs from record snapshot")
            prior = latest.get(action_id)
            if prior is None:
                if record.revision != 1:
                    raise ControlPlaneActionLedgerError("first action record revision must be one")
            else:
                if record.revision != prior.revision + 1:
                    raise ControlPlaneActionLedgerError("action revisions are not contiguous")
                if record.request_fingerprint != prior.request_fingerprint:
                    raise ControlPlaneActionLedgerError("action request mutated across revisions")
                if record.created_at_utc != prior.created_at_utc:
                    raise ControlPlaneActionLedgerError("action creation timestamp mutated")
                if record.updated_at_utc < prior.updated_at_utc:
                    raise ControlPlaneActionLedgerError("action update time moved backward")
            owner = idempotency_owner.get(record.request.idempotency_key)
            if owner is not None and owner != action_id:
                raise ControlPlaneActionLedgerError(
                    "idempotency key is associated with multiple actions"
                )
            idempotency_owner[record.request.idempotency_key] = action_id
            latest[action_id] = record
        return latest

    def get(self, action_id: str) -> ControlPlaneActionRecord:
        record = self.records().get(action_id)
        if record is None:
            raise ControlPlaneActionNotFound(action_id)
        return record

    def create_request(self, request: ControlPlaneActionRequest) -> ControlPlaneActionRecord:
        with self._lock:
            existing = self.records()
            fingerprint = request.authority_fingerprint()
            for record in existing.values():
                if record.request.idempotency_key == request.idempotency_key:
                    if record.request_fingerprint != fingerprint:
                        raise ControlPlaneActionConflict(
                            "idempotency key was already used for a different action request"
                        )
                    return record
            collision = existing.get(request.action_id)
            if collision is not None:
                if collision.request_fingerprint == fingerprint:
                    return collision
                raise ControlPlaneActionConflict("action_id already belongs to another request")

            now = self._now()
            scope = required_confirmation_scope(request.action_kind)
            state = (
                ControlPlaneActionState.AUTHORIZED
                if scope is None
                else ControlPlaneActionState.AWAITING_CONFIRMATION
            )
            record = ControlPlaneActionRecord(
                request=request,
                request_fingerprint=fingerprint,
                state=state,
                revision=1,
                created_at_utc=now,
                updated_at_utc=now,
                confirmation_scope=scope,
                confirmation=None,
                provider_write_attempted=False,
                provider_write_uncertain=False,
            )
            self.audit_log.append(
                event_type=ControlPlaneAuditEventType.ACTION_REQUESTED,
                actor="local_user",
                action_id=request.action_id,
                action_fingerprint=fingerprint,
                action_state=record.state,
                details={"record": record.model_dump(mode="json")},
            )
            return record

    def confirm(
        self,
        action_id: str,
        grant: ControlPlaneConfirmationGrant,
    ) -> ControlPlaneActionRecord:
        with self._lock:
            record = self.get(action_id)
            if record.confirmation is not None:
                if record.confirmation == grant and record.state == ControlPlaneActionState.AUTHORIZED:
                    return record
                raise ControlPlaneActionConflict("action confirmation has already been consumed")
            if record.state != ControlPlaneActionState.AWAITING_CONFIRMATION:
                raise ControlPlaneActionConflict(
                    f"action is not awaiting confirmation: {record.state}"
                )
            if not confirmation_matches_request(record.request, grant):
                raise ControlPlaneActionConflict(
                    "confirmation does not bind the exact requested action"
                )
            now = self._now()
            updated = record.model_copy(
                update={
                    "state": ControlPlaneActionState.AUTHORIZED,
                    "revision": record.revision + 1,
                    "updated_at_utc": now,
                    "confirmation": grant,
                }
            )
            updated = ControlPlaneActionRecord.model_validate(updated.model_dump(mode="python"))
            self.audit_log.append(
                event_type=ControlPlaneAuditEventType.ACTION_CONFIRMATION_GRANTED,
                actor="local_user",
                action_id=updated.request.action_id,
                action_fingerprint=updated.request_fingerprint,
                action_state=updated.state,
                details={"record": updated.model_dump(mode="json")},
            )
            return updated

    def verify(self) -> dict[str, object]:
        records = self.records()
        events = self.audit_log.read_verified()
        uncertain = [
            record.request.action_id
            for record in records.values()
            if record.provider_write_uncertain
        ]
        return {
            "event_count": len(events),
            "action_count": len(records),
            "uncertain_action_count": len(uncertain),
            "uncertain_action_ids": tuple(sorted(uncertain)),
            "hash_chain_valid": True,
            "idempotency_unique": True,
            "pass": True,
        }
