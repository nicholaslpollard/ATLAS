from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.control_plane import ControlPlaneActionKind
from packages.schemas.execution import (
    BrokerName,
    BrokerOrderSide,
    BrokerOrderStatus,
    ExecutionEnvironment,
)


CONTROL_PLANE_CLEANUP_PLAN_CONTRACT_VERSION = (
    "control-plane-cleanup-plan-v1-reconciled-exact-resource-review-no-provider-authority"
)
CONTROL_PLANE_CLEANUP_PLAN_CONFIRMATION_CONTRACT_VERSION = (
    "control-plane-cleanup-plan-confirmation-v1-action-and-plan-fingerprint-bound"
)


class ControlPlaneCleanupPlanKind(StrEnum):
    CANCEL_OPEN_ORDERS = "CANCEL_OPEN_ORDERS"
    FLATTEN_POSITIONS = "FLATTEN_POSITIONS"


class ControlPlaneCancelOrderTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str = Field(min_length=8, max_length=32)
    ticker: str = Field(min_length=1, max_length=64)
    side: BrokerOrderSide
    status: BrokerOrderStatus
    requested_quantity: float = Field(gt=0.0)
    filled_quantity: float = Field(ge=0.0)
    updated_at_utc: datetime

    @model_validator(mode="after")
    def _validate_target(self) -> "ControlPlaneCancelOrderTarget":
        if self.updated_at_utc.tzinfo is None:
            raise ValueError("cancel target timestamp must be timezone-aware")
        if self.filled_quantity > self.requested_quantity + 1e-12:
            raise ValueError("cancel target filled quantity cannot exceed requested quantity")
        if self.status not in {
            BrokerOrderStatus.SUBMITTED,
            BrokerOrderStatus.PARTIAL_FILLED,
        }:
            raise ValueError("cleanup cancel target must represent an open order")
        return self


class ControlPlaneFlattenPositionTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str = Field(min_length=1, max_length=64)
    quantity: float
    market_value: float
    average_entry_price: float | None = Field(default=None, gt=0.0)
    required_close_side: BrokerOrderSide
    as_of_utc: datetime

    @model_validator(mode="after")
    def _validate_target(self) -> "ControlPlaneFlattenPositionTarget":
        if self.as_of_utc.tzinfo is None:
            raise ValueError("flatten target timestamp must be timezone-aware")
        if abs(self.quantity) <= 1e-12:
            raise ValueError("flatten target quantity must be nonzero")
        expected = (
            BrokerOrderSide.SELL
            if self.quantity > 0
            else BrokerOrderSide.BUY_TO_COVER
        )
        if self.required_close_side != expected:
            raise ValueError("flatten target close side does not match signed position quantity")
        return self


class ControlPlaneCleanupPlan(BaseModel):
    """Immutable review artifact derived from one fresh broker reconciliation.

    Phase 16 v1 deliberately grants no provider-write authority. A later accepted mutation
    processor must re-check the exact resource set and require a plan-bound confirmation.
    """

    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_CLEANUP_PLAN_CONTRACT_VERSION] = (
        CONTROL_PLANE_CLEANUP_PLAN_CONTRACT_VERSION
    )
    action_id: str = Field(min_length=1, max_length=64)
    action_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_kind: ControlPlaneActionKind
    plan_kind: ControlPlaneCleanupPlanKind
    broker: BrokerName
    environment: Literal[ExecutionEnvironment.PAPER] = ExecutionEnvironment.PAPER
    account_ref: str = Field(pattern=r"^[0-9a-f]{16}$")
    generated_at_utc: datetime
    expires_at_utc: datetime
    reconciliation_as_of_utc: datetime
    zero_open_orders: bool
    zero_positions: bool
    cancel_targets: tuple[ControlPlaneCancelOrderTarget, ...] = ()
    flatten_targets: tuple[ControlPlaneFlattenPositionTarget, ...] = ()
    no_op: bool
    exact_resource_set_recheck_required: Literal[True] = True
    exact_plan_confirmation_required: Literal[True] = True
    scope_expansion_allowed: Literal[False] = False
    provider_write_authorized: Literal[False] = False
    flatten_close_order_method_accepted: Literal[False] = False
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_plan(self) -> "ControlPlaneCleanupPlan":
        for value in (
            self.generated_at_utc,
            self.expires_at_utc,
            self.reconciliation_as_of_utc,
        ):
            if value.tzinfo is None:
                raise ValueError("cleanup plan timestamps must be timezone-aware")
        if self.expires_at_utc <= self.generated_at_utc:
            raise ValueError("cleanup plan expiry must be after generation")
        if self.reconciliation_as_of_utc > self.generated_at_utc:
            raise ValueError("cleanup reconciliation cannot occur after plan generation")
        if self.broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
            raise ValueError("cleanup plans support only Webull/Alpaca paper brokers")
        if not self.reason_codes:
            raise ValueError("cleanup plan requires reason codes")

        if self.plan_kind == ControlPlaneCleanupPlanKind.CANCEL_OPEN_ORDERS:
            if self.action_kind != ControlPlaneActionKind.CANCEL_OPEN_ORDERS:
                raise ValueError("cancel plan kind must bind a cancel-open-orders action")
            if self.flatten_targets:
                raise ValueError("cancel plan cannot contain flatten targets")
            if self.zero_open_orders != (len(self.cancel_targets) == 0):
                raise ValueError("zero_open_orders must match cancel target inventory")
            if self.no_op != self.zero_open_orders:
                raise ValueError("cancel plan no_op must mean there are no open orders")
        elif self.plan_kind == ControlPlaneCleanupPlanKind.FLATTEN_POSITIONS:
            if self.action_kind != ControlPlaneActionKind.FLATTEN_POSITIONS:
                raise ValueError("flatten plan kind must bind a flatten-positions action")
            if self.cancel_targets:
                raise ValueError("flatten plan cannot contain cancel targets")
            if not self.zero_open_orders:
                raise ValueError("flatten plan requires zero open orders before position close planning")
            if self.zero_positions != (len(self.flatten_targets) == 0):
                raise ValueError("zero_positions must match flatten target inventory")
            if self.no_op != self.zero_positions:
                raise ValueError("flatten plan no_op must mean there are no positions")
        else:
            raise ValueError("unsupported cleanup plan kind")
        return self

    def plan_fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class ControlPlaneCleanupPlanConfirmationGrant(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_CLEANUP_PLAN_CONFIRMATION_CONTRACT_VERSION] = (
        CONTROL_PLANE_CLEANUP_PLAN_CONFIRMATION_CONTRACT_VERSION
    )
    grant_id: str = Field(min_length=1, max_length=64)
    action_id: str = Field(min_length=1, max_length=64)
    action_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    cleanup_plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_by: Literal["local_user"] = "local_user"
    confirmed_at_utc: datetime
    one_time: Literal[True] = True

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "ControlPlaneCleanupPlanConfirmationGrant":
        if self.confirmed_at_utc.tzinfo is None:
            raise ValueError("cleanup plan confirmation timestamp must be timezone-aware")
        return self


def cleanup_plan_confirmation_matches(
    plan: ControlPlaneCleanupPlan,
    grant: ControlPlaneCleanupPlanConfirmationGrant,
) -> bool:
    return bool(
        grant.one_time is True
        and grant.action_id == plan.action_id
        and grant.action_fingerprint == plan.action_fingerprint
        and grant.cleanup_plan_fingerprint == plan.plan_fingerprint()
    )
