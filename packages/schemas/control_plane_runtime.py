from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.execution import BrokerName, ExecutionEnvironment


CONTROL_PLANE_RUNTIME_CONTRACT_VERSION = (
    "control-plane-runtime-v2-explicit-selection-audit-bound-uncertainty-fail-closed"
)


class ControlPlaneRuntimeState(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_RUNTIME_CONTRACT_VERSION] = (
        CONTROL_PLANE_RUNTIME_CONTRACT_VERSION
    )
    revision: int = Field(default=0, ge=0)
    updated_at_utc: datetime
    selected_broker: BrokerName | None = None
    selected_environment: ExecutionEnvironment | None = None
    provider_write_uncertain: bool = False
    active_action_id: str | None = Field(default=None, min_length=1, max_length=64)
    uncertain_action_id: str | None = Field(default=None, min_length=1, max_length=64)
    last_transition_action_id: str | None = Field(default=None, min_length=1, max_length=64)
    last_transition_audit_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source: Literal["synthetic_default", "persisted"]

    @model_validator(mode="after")
    def _validate_runtime_authority(self) -> "ControlPlaneRuntimeState":
        if self.updated_at_utc.tzinfo is None:
            raise ValueError("updated_at_utc must be timezone-aware")
        if (self.selected_broker is None) != (self.selected_environment is None):
            raise ValueError("broker and environment selection must be set or unset together")
        if self.selected_environment == ExecutionEnvironment.LIVE:
            raise ValueError("Phase 16 runtime state cannot select live execution")
        if self.selected_environment == ExecutionEnvironment.SHADOW:
            if self.selected_broker != BrokerName.SHADOW:
                raise ValueError("shadow environment requires shadow broker")
        if self.selected_environment == ExecutionEnvironment.PAPER:
            if self.selected_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
                raise ValueError("paper environment requires Webull or Alpaca")
        if self.provider_write_uncertain != (self.uncertain_action_id is not None):
            raise ValueError(
                "provider_write_uncertain must exactly track an uncertain action id"
            )
        if self.uncertain_action_id is not None and self.active_action_id is not None:
            raise ValueError("uncertain runtime state cannot also claim an active action")
        if (self.last_transition_action_id is None) != (
            self.last_transition_audit_hash is None
        ):
            raise ValueError("runtime transition action/hash must be set or unset together")
        if self.source == "synthetic_default":
            if self.revision != 0:
                raise ValueError("synthetic default runtime state must have revision zero")
            if self.selected_broker is not None or self.selected_environment is not None:
                raise ValueError("synthetic default must not auto-select execution routing")
            if self.active_action_id is not None or self.uncertain_action_id is not None:
                raise ValueError("synthetic default cannot contain action state")
            if self.provider_write_uncertain:
                raise ValueError("synthetic default cannot contain provider uncertainty")
            if self.last_transition_action_id is not None:
                raise ValueError("synthetic default cannot claim an audit-bound transition")
        else:
            if self.revision < 1:
                raise ValueError("persisted runtime state must have revision at least one")
            if self.last_transition_action_id is None:
                raise ValueError("persisted runtime state must be audit-bound")
        return self

    def authority_fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def synthetic_default(cls, *, now_utc: datetime | None = None) -> "ControlPlaneRuntimeState":
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        return cls(
            revision=0,
            updated_at_utc=now,
            selected_broker=None,
            selected_environment=None,
            provider_write_uncertain=False,
            active_action_id=None,
            uncertain_action_id=None,
            last_transition_action_id=None,
            last_transition_audit_hash=None,
            source="synthetic_default",
        )
