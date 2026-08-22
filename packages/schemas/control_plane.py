from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.execution import BrokerName, ExecutionEnvironment


CONTROL_PLANE_ACTION_CONTRACT_VERSION = (
    "control-plane-action-v1-explicit-local-user-idempotent-confirmation-bound"
)
CONTROL_PLANE_CONFIRMATION_CONTRACT_VERSION = (
    "control-plane-confirmation-v1-one-time-action-fingerprint-bound"
)


class ControlPlaneActionKind(StrEnum):
    BROKER_SWITCH = "BROKER_SWITCH"
    CANCEL_OPEN_ORDERS = "CANCEL_OPEN_ORDERS"
    FLATTEN_POSITIONS = "FLATTEN_POSITIONS"
    EXECUTE_SHADOW = "EXECUTE_SHADOW"
    EXECUTE_PAPER = "EXECUTE_PAPER"


class ControlPlaneActionState(StrEnum):
    REQUESTED = "REQUESTED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"


class ControlPlaneConfirmationScope(StrEnum):
    BROKER_SWITCH = "BROKER_SWITCH"
    CANCEL_OPEN_ORDERS = "CANCEL_OPEN_ORDERS"
    FLATTEN_POSITIONS = "FLATTEN_POSITIONS"
    PAPER_EXECUTION = "PAPER_EXECUTION"


class ControlPlaneActionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_ACTION_CONTRACT_VERSION] = (
        CONTROL_PLANE_ACTION_CONTRACT_VERSION
    )
    action_id: str = Field(min_length=1, max_length=64)
    action_kind: ControlPlaneActionKind
    requested_by: Literal["local_user"] = "local_user"
    requested_at_utc: datetime
    explicit_user_request: Literal[True] = True
    idempotency_key: str = Field(min_length=1, max_length=128)
    target_broker: BrokerName | None = None
    environment: ExecutionEnvironment | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_authority_shape(self) -> "ControlPlaneActionRequest":
        if self.requested_at_utc.tzinfo is None:
            raise ValueError("requested_at_utc must be timezone-aware")
        if self.environment == ExecutionEnvironment.LIVE:
            raise ValueError("Phase 16 cannot request live execution")
        if self.action_kind == ControlPlaneActionKind.BROKER_SWITCH:
            if self.target_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
                raise ValueError("broker switch target must be Webull or Alpaca")
            if self.environment != ExecutionEnvironment.PAPER:
                raise ValueError("Webull/Alpaca broker switching is paper-only in Phase 16")
        elif self.action_kind in {
            ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
            ControlPlaneActionKind.FLATTEN_POSITIONS,
        }:
            if self.target_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
                raise ValueError("broker mutation requires an explicit Webull or Alpaca target")
            if self.environment != ExecutionEnvironment.PAPER:
                raise ValueError("broker mutation is accepted only for the paper environment in Phase 16")
        elif self.action_kind == ControlPlaneActionKind.EXECUTE_SHADOW:
            if self.environment != ExecutionEnvironment.SHADOW or self.target_broker != BrokerName.SHADOW:
                raise ValueError("shadow execution must target the shadow broker")
        elif self.action_kind == ControlPlaneActionKind.EXECUTE_PAPER:
            if self.environment != ExecutionEnvironment.PAPER:
                raise ValueError("paper execution must use the paper environment")
            if self.target_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
                raise ValueError("paper execution target must be Webull or Alpaca")
        return self

    def authority_fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class ControlPlaneConfirmationGrant(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_CONFIRMATION_CONTRACT_VERSION] = (
        CONTROL_PLANE_CONFIRMATION_CONTRACT_VERSION
    )
    grant_id: str = Field(min_length=1, max_length=64)
    action_id: str = Field(min_length=1, max_length=64)
    action_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: ControlPlaneConfirmationScope
    confirmed_by: Literal["local_user"] = "local_user"
    confirmed_at_utc: datetime
    one_time: Literal[True] = True

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "ControlPlaneConfirmationGrant":
        if self.confirmed_at_utc.tzinfo is None:
            raise ValueError("confirmed_at_utc must be timezone-aware")
        return self


def required_confirmation_scope(
    action_kind: ControlPlaneActionKind,
) -> ControlPlaneConfirmationScope | None:
    return {
        ControlPlaneActionKind.BROKER_SWITCH: ControlPlaneConfirmationScope.BROKER_SWITCH,
        ControlPlaneActionKind.CANCEL_OPEN_ORDERS: ControlPlaneConfirmationScope.CANCEL_OPEN_ORDERS,
        ControlPlaneActionKind.FLATTEN_POSITIONS: ControlPlaneConfirmationScope.FLATTEN_POSITIONS,
        ControlPlaneActionKind.EXECUTE_PAPER: ControlPlaneConfirmationScope.PAPER_EXECUTION,
        ControlPlaneActionKind.EXECUTE_SHADOW: None,
    }[action_kind]


def confirmation_matches_request(
    request: ControlPlaneActionRequest,
    grant: ControlPlaneConfirmationGrant,
) -> bool:
    required = required_confirmation_scope(request.action_kind)
    return bool(
        required is not None
        and grant.action_id == request.action_id
        and grant.action_fingerprint == request.authority_fingerprint()
        and grant.scope == required
        and grant.one_time is True
    )
