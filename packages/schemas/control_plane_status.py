from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.execution import (
    BrokerName,
    BrokerOrderSide,
    BrokerOrderStatus,
    ExecutionEnvironment,
)


CONTROL_PLANE_STATUS_CONTRACT_VERSION = (
    "control-plane-status-v1-readonly-sanitized-lineage-broker-state"
)


class ControlPlaneReadState(StrEnum):
    UNPOLLED = "UNPOLLED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ControlPlaneHealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class CredentialPresence(BaseModel):
    model_config = ConfigDict(frozen=True)

    required_names: tuple[str, ...]
    optional_names: tuple[str, ...] = ()
    required_present: dict[str, bool]
    optional_present: dict[str, bool] = Field(default_factory=dict)
    ready: bool

    @model_validator(mode="after")
    def _validate_no_values(self) -> "CredentialPresence":
        if set(self.required_present) != set(self.required_names):
            raise ValueError("required credential presence map does not match required names")
        if set(self.optional_present) != set(self.optional_names):
            raise ValueError("optional credential presence map does not match optional names")
        if self.ready != all(self.required_present.values()):
            raise ValueError("credential readiness must be derived only from required presence")
        return self


class PublicBrokerAccountStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_ref: str = Field(pattern=r"^[0-9a-f]{16}$")
    as_of_utc: datetime
    equity: float
    cash: float
    buying_power: float
    gross_market_value: float
    trading_blocked: bool
    shorting_enabled: bool | None = None

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "PublicBrokerAccountStatus":
        if self.as_of_utc.tzinfo is None:
            raise ValueError("as_of_utc must be timezone-aware")
        return self


class PublicBrokerPositionStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str = Field(min_length=1)
    quantity: float
    market_value: float
    average_entry_price: float | None = None
    as_of_utc: datetime

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "PublicBrokerPositionStatus":
        if self.as_of_utc.tzinfo is None:
            raise ValueError("position as_of_utc must be timezone-aware")
        return self


class PublicBrokerOrderStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str = Field(min_length=1, max_length=128)
    ticker: str = Field(min_length=1)
    side: BrokerOrderSide
    status: BrokerOrderStatus
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float | None = None
    submitted_at_utc: datetime | None = None
    updated_at_utc: datetime

    @model_validator(mode="after")
    def _validate_timestamps(self) -> "PublicBrokerOrderStatus":
        if self.submitted_at_utc is not None and self.submitted_at_utc.tzinfo is None:
            raise ValueError("submitted_at_utc must be timezone-aware")
        if self.updated_at_utc.tzinfo is None:
            raise ValueError("updated_at_utc must be timezone-aware")
        return self


class BrokerReadStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_STATUS_CONTRACT_VERSION] = (
        CONTROL_PLANE_STATUS_CONTRACT_VERSION
    )
    broker: BrokerName
    environment: ExecutionEnvironment
    state: ControlPlaneReadState
    credentials: CredentialPresence
    polled_at_utc: datetime | None = None
    account: PublicBrokerAccountStatus | None = None
    positions: tuple[PublicBrokerPositionStatus, ...] = ()
    open_orders: tuple[PublicBrokerOrderStatus, ...] = ()
    reconciled: bool | None = None
    zero_open_orders: bool | None = None
    zero_positions: bool | None = None
    safe_to_switch_broker: bool | None = None
    error_code: str | None = None
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def _validate_state(self) -> "BrokerReadStatus":
        if self.environment != ExecutionEnvironment.PAPER:
            raise ValueError("Phase 16 provider broker status is paper-only")
        if self.broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
            raise ValueError("Phase 16 provider broker status supports only Webull/Alpaca")
        if self.state == ControlPlaneReadState.AVAILABLE:
            if self.polled_at_utc is None or self.account is None:
                raise ValueError("available broker state requires poll time and account")
            if self.error_code is not None:
                raise ValueError("available broker state cannot carry an error")
            if self.reconciled is not True:
                raise ValueError("available broker state must be reconciled")
            if self.zero_open_orders != (len(self.open_orders) == 0):
                raise ValueError("zero_open_orders must match open order snapshot")
            if self.zero_positions != (len(self.positions) == 0):
                raise ValueError("zero_positions must match position snapshot")
            expected_safe = bool(self.reconciled and self.zero_open_orders and self.zero_positions)
            if self.safe_to_switch_broker != expected_safe:
                raise ValueError("safe_to_switch_broker must match reconciliation state")
        else:
            if self.account is not None or self.positions or self.open_orders:
                raise ValueError("non-available broker state cannot expose partial provider state")
            if any(
                value is not None
                for value in (
                    self.reconciled,
                    self.zero_open_orders,
                    self.zero_positions,
                    self.safe_to_switch_broker,
                )
            ):
                raise ValueError("non-available broker state cannot claim reconciliation state")
        if self.polled_at_utc is not None and self.polled_at_utc.tzinfo is None:
            raise ValueError("polled_at_utc must be timezone-aware")
        return self


class Phase15AcceptanceStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_STATUS_CONTRACT_VERSION] = (
        CONTROL_PLANE_STATUS_CONTRACT_VERSION
    )
    artifact_present: bool
    accepted: bool
    as_of_date: str | None = None
    policy_fingerprint: str | None = None
    cumulative_foundation_fingerprint: str | None = None
    execution_case_count: int | None = None
    actual_broker_execution_exercised: bool | None = None
    live_execution_promoted: bool | None = None
    error_code: str | None = None


class ControlPlaneSystemStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_STATUS_CONTRACT_VERSION] = (
        CONTROL_PLANE_STATUS_CONTRACT_VERSION
    )
    generated_at_utc: datetime
    health: ControlPlaneHealthState
    phase16_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_phase15_merge_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    accepted_phase15_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    primary_broker: Literal["webull"] = "webull"
    secondary_broker: Literal["alpaca"] = "alpaca"
    selected_broker: BrokerName | None = None
    selected_environment: ExecutionEnvironment | None = None
    runtime_state_valid: bool
    runtime_state_source: Literal["synthetic_default", "persisted", "invalid"]
    runtime_revision: int | None = Field(default=None, ge=0)
    provider_write_uncertain: bool
    active_action_present: bool
    uncertain_action_present: bool
    allowed_execution_environments: tuple[str, str]
    live_execution_promoted: Literal[False] = False
    automatic_cross_broker_failover_allowed: Literal[False] = False
    browser_is_execution_authority: Literal[False] = False
    credentials_exposed: Literal[False] = False
    write_actions_enabled: bool = False
    bind_host_default: Literal["127.0.0.1"] = "127.0.0.1"
    phase15: Phase15AcceptanceStatus

    @model_validator(mode="after")
    def _validate_system_state(self) -> "ControlPlaneSystemStatus":
        if self.allowed_execution_environments != ("shadow", "paper"):
            raise ValueError("Phase 16 allowed environments must remain shadow/paper")
        if (self.selected_broker is None) != (self.selected_environment is None):
            raise ValueError("selected broker/environment must be set or unset together")
        if not self.runtime_state_valid:
            if self.runtime_state_source != "invalid" or self.runtime_revision is not None:
                raise ValueError("invalid runtime state must not claim a revision")
            if self.selected_broker is not None or self.selected_environment is not None:
                raise ValueError("invalid runtime state cannot supply execution routing")
            if not self.provider_write_uncertain:
                raise ValueError("invalid runtime state must fail closed as uncertain")
        return self


class ControlPlaneExecutionStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: Literal[CONTROL_PLANE_STATUS_CONTRACT_VERSION] = (
        CONTROL_PLANE_STATUS_CONTRACT_VERSION
    )
    phase15_accepted: bool
    phase15_as_of_date: str | None = None
    phase15_execution_case_count: int | None = None
    selected_broker: BrokerName | None = None
    selected_environment: ExecutionEnvironment | None = None
    provider_write_uncertain: bool = False
    shadow_execution_available_by_policy: Literal[True] = True
    paper_execution_available_by_policy: Literal[True] = True
    live_execution_available_by_policy: Literal[False] = False
    write_endpoints_present: Literal[False] = False
    automatic_failover_present: Literal[False] = False
    current_action_count: int = Field(default=0, ge=0)
    uncertain_action_count: int = Field(default=0, ge=0)
