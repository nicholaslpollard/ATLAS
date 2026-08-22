from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.control_plane import (
    ControlPlaneActionRequest,
    ControlPlaneActionState,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
    confirmation_matches_request,
    required_confirmation_scope,
)


CONTROL_PLANE_ACTION_RECORD_CONTRACT_VERSION = (
    "control-plane-action-record-v1-idempotent-confirmed-provider-uncertainty"
)
CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION = (
    "control-plane-audit-event-v1-hash-chain-append-only"
)
ZERO_AUDIT_HASH = "0" * 64


class ControlPlaneAuditEventType(StrEnum):
    ACTION_REQUESTED = "ACTION_REQUESTED"
    ACTION_CONFIRMATION_GRANTED = "ACTION_CONFIRMATION_GRANTED"
    ACTION_STATE_CHANGED = "ACTION_STATE_CHANGED"
    PROVIDER_WRITE_ATTEMPTED = "PROVIDER_WRITE_ATTEMPTED"
    PROVIDER_WRITE_RECONCILED = "PROVIDER_WRITE_RECONCILED"
    RUNTIME_STATE_CHANGED = "RUNTIME_STATE_CHANGED"


class ControlPlaneActionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_ACTION_RECORD_CONTRACT_VERSION] = (
        CONTROL_PLANE_ACTION_RECORD_CONTRACT_VERSION
    )
    request: ControlPlaneActionRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: ControlPlaneActionState
    revision: int = Field(ge=1)
    created_at_utc: datetime
    updated_at_utc: datetime
    confirmation_scope: ControlPlaneConfirmationScope | None = None
    confirmation: ControlPlaneConfirmationGrant | None = None
    provider_write_attempted: bool = False
    provider_write_uncertain: bool = False
    error_code: str | None = Field(default=None, max_length=128)
    result_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_record(self) -> "ControlPlaneActionRecord":
        if self.created_at_utc.tzinfo is None or self.updated_at_utc.tzinfo is None:
            raise ValueError("action record timestamps must be timezone-aware")
        if self.updated_at_utc < self.created_at_utc:
            raise ValueError("action record cannot update before creation")
        if self.request_fingerprint != self.request.authority_fingerprint():
            raise ValueError("action record request fingerprint mismatch")
        required = required_confirmation_scope(self.request.action_kind)
        if self.confirmation_scope != required:
            raise ValueError("action confirmation scope differs from action policy")
        if self.confirmation is not None:
            if required is None:
                raise ValueError("action without confirmation requirement cannot carry a grant")
            if not confirmation_matches_request(self.request, self.confirmation):
                raise ValueError("confirmation grant does not bind exact action request")
        if self.state == ControlPlaneActionState.AWAITING_CONFIRMATION:
            if required is None or self.confirmation is not None:
                raise ValueError("awaiting-confirmation state has invalid confirmation shape")
        if self.state == ControlPlaneActionState.AUTHORIZED:
            if required is not None and self.confirmation is None:
                raise ValueError("confirmed action cannot be authorized without exact grant")
        if self.provider_write_uncertain:
            if not self.provider_write_attempted or self.state != ControlPlaneActionState.UNCERTAIN:
                raise ValueError("provider write uncertainty requires attempted UNCERTAIN state")
        if self.state == ControlPlaneActionState.UNCERTAIN and not self.provider_write_uncertain:
            raise ValueError("UNCERTAIN state must carry provider write uncertainty")
        if self.state in {ControlPlaneActionState.COMPLETED, ControlPlaneActionState.FAILED}:
            if self.provider_write_uncertain:
                raise ValueError("terminal known state cannot retain write uncertainty")
        return self


class ControlPlaneAuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION] = (
        CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION
    )
    sequence: int = Field(ge=1)
    event_id: str = Field(min_length=8, max_length=64)
    event_type: ControlPlaneAuditEventType
    occurred_at_utc: datetime
    actor: Literal["local_user", "atlas_system"]
    action_id: str | None = Field(default=None, min_length=1, max_length=64)
    action_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    action_state: ControlPlaneActionState | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_event(self) -> "ControlPlaneAuditEvent":
        if self.occurred_at_utc.tzinfo is None:
            raise ValueError("audit event timestamp must be timezone-aware")
        if (self.action_id is None) != (self.action_fingerprint is None):
            raise ValueError("action audit event must carry id and fingerprint together")
        if self.event_hash != self.compute_hash():
            raise ValueError("audit event hash mismatch")
        return self

    def hash_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "sequence": self.sequence,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at_utc": self.occurred_at_utc.isoformat(),
            "actor": self.actor,
            "action_id": self.action_id,
            "action_fingerprint": self.action_fingerprint,
            "action_state": self.action_state.value if self.action_state is not None else None,
            "details": self.details,
            "previous_event_hash": self.previous_event_hash,
        }

    def compute_hash(self) -> str:
        raw = json.dumps(
            self.hash_payload(), sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
