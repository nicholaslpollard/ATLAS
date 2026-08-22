from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.discovery_score import DiscoveryDirection


EXECUTION_INTENT_CONTRACT_VERSION = (
    "execution-intent-v1-phase13-reference-plan-fresh-quote-risk-bounded"
)
BROKER_ACCOUNT_CONTRACT_VERSION = "broker-account-v1-broker-neutral-reconciliation"
BROKER_ORDER_PLAN_CONTRACT_VERSION = "broker-order-plan-v1-equity-limit-protective-bracket"
BROKER_PREFLIGHT_CONTRACT_VERSION = "broker-preflight-v1-provider-normalized"
BROKER_ORDER_SNAPSHOT_CONTRACT_VERSION = "broker-order-snapshot-v1-provider-normalized"
BROKER_POSITION_SNAPSHOT_CONTRACT_VERSION = "broker-position-snapshot-v1-provider-normalized"
BROKER_RECONCILIATION_CONTRACT_VERSION = "broker-reconciliation-v1-orders-positions-account"
EXECUTION_OUTCOME_CONTRACT_VERSION = "execution-outcome-v1-realized-descriptive-no-authority"


class ExecutionEnvironment(StrEnum):
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE = "live"


class BrokerName(StrEnum):
    WEBULL = "webull"
    ALPACA = "alpaca"
    SHADOW = "shadow"


class BrokerOrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    BUY_TO_COVER = "BUY_TO_COVER"


class BrokerOrderStatus(StrEnum):
    PLANNED = "PLANNED"
    PREFLIGHTED = "PREFLIGHTED"
    SUBMITTED = "SUBMITTED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    SHADOW_FILLED = "SHADOW_FILLED"


class ExecutionExitReason(StrEnum):
    STOP = "STOP"
    TARGET = "TARGET"
    MANUAL = "MANUAL"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("execution timestamps must be timezone-aware")
    return value.astimezone(UTC)


class ExecutionIntent(BaseModel):
    """Immutable translation from an accepted research plan to an executable plan.

    This is not a broker acknowledgement. It expresses the exact prices/quantity ATLAS
    is allowed to submit after the independent broker preflight and reconciliation gates.
    """

    model_config = ConfigDict(frozen=True)

    contract_version: str = EXECUTION_INTENT_CONTRACT_VERSION
    intent_id: str = Field(min_length=16, max_length=128)
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    direction: DiscoveryDirection
    environment: ExecutionEnvironment
    broker: BrokerName
    phase13_case_sha256: str = Field(min_length=64, max_length=64)
    phase14_acceptance_sha256: str = Field(min_length=64, max_length=64)

    reference_entry: float = Field(gt=0.0)
    entry_limit: float = Field(gt=0.0)
    stop: float = Field(gt=0.0)
    target: float = Field(gt=0.0)
    original_risk_per_share: float = Field(gt=0.0)
    executable_risk_per_share: float = Field(gt=0.0)
    executable_reward_per_share: float = Field(gt=0.0)
    adverse_entry_drift_r: float = Field(ge=0.0)
    executable_reward_to_risk: float = Field(gt=0.0)
    accepted_risk_budget: float = Field(gt=0.0)
    accepted_proposed_quantity: int = Field(ge=1)
    executable_quantity: int = Field(ge=1)

    quote_bid: float = Field(gt=0.0)
    quote_ask: float = Field(gt=0.0)
    quote_provider_timestamp_utc: datetime
    quote_received_at_utc: datetime
    quote_feed_mode: str = Field(min_length=1)
    quote_expected_delay_seconds: int = Field(ge=0)
    quote_age_seconds: float = Field(ge=0.0)
    session_segment: str = Field(min_length=1)

    order_type: str = Field(pattern="^LIMIT$")
    time_in_force: str = Field(pattern="^DAY$")
    extended_hours: bool = False
    protective_stop_required: bool = True
    profit_target_required: bool = True
    broker_preflight_required: bool = True
    reconciliation_required: bool = True
    live_execution_enabled: bool = False

    reason_codes: tuple[str, ...]

    @field_validator("instrument_id", "ticker", "intent_id")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("execution identity text cannot be blank")
        return cleaned

    @field_validator("quote_provider_timestamp_utc", "quote_received_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_intent(self) -> "ExecutionIntent":
        if self.quote_ask < self.quote_bid:
            raise ValueError("execution quote ask cannot be below bid")
        if self.environment == ExecutionEnvironment.LIVE and not self.live_execution_enabled:
            raise ValueError("live execution intent is disabled")
        if self.environment == ExecutionEnvironment.SHADOW and self.broker != BrokerName.SHADOW:
            raise ValueError("shadow intent must use the shadow broker")
        if self.environment == ExecutionEnvironment.PAPER and self.broker == BrokerName.SHADOW:
            raise ValueError("paper intent requires a real paper/sandbox broker adapter")
        if self.executable_quantity > self.accepted_proposed_quantity:
            raise ValueError("executable quantity cannot exceed accepted Phase 13 proposed quantity")
        if self.direction == DiscoveryDirection.BULLISH:
            if not self.stop < self.entry_limit < self.target:
                raise ValueError("LONG executable geometry must satisfy stop < entry < target")
        elif self.direction == DiscoveryDirection.BEARISH:
            if not self.stop > self.entry_limit > self.target:
                raise ValueError("SHORT executable geometry must satisfy stop > entry > target")
        else:
            raise ValueError("execution intent cannot be neutral")
        if self.extended_hours:
            raise ValueError("Phase 15 v1 extended-hours execution is disabled")
        if not self.protective_stop_required or not self.profit_target_required:
            raise ValueError("Phase 15 executable plan requires stop and target")
        if not self.broker_preflight_required or not self.reconciliation_required:
            raise ValueError("Phase 15 executable plan requires preflight and reconciliation")
        if not self.reason_codes:
            raise ValueError("execution intent requires reason codes")
        return self


class BrokerOrderPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_ORDER_PLAN_CONTRACT_VERSION
    intent_id: str = Field(min_length=16, max_length=128)
    client_order_id: str = Field(min_length=8, max_length=128)
    ticker: str = Field(min_length=1, max_length=64)
    instrument_type: str = Field(pattern="^EQUITY$")
    side: BrokerOrderSide
    quantity: int = Field(ge=1)
    order_type: str = Field(pattern="^LIMIT$")
    limit_price: float = Field(gt=0.0)
    stop_price: float = Field(gt=0.0)
    target_price: float = Field(gt=0.0)
    time_in_force: str = Field(pattern="^DAY$")
    extended_hours: bool = False
    bracket_required: bool = True

    @model_validator(mode="after")
    def validate_plan(self) -> "BrokerOrderPlan":
        if self.side == BrokerOrderSide.BUY:
            if not self.stop_price < self.limit_price < self.target_price:
                raise ValueError("buy bracket geometry is invalid")
        elif self.side == BrokerOrderSide.SHORT:
            if not self.stop_price > self.limit_price > self.target_price:
                raise ValueError("short bracket geometry is invalid")
        else:
            raise ValueError("Phase 15 entry side must be BUY or SHORT")
        if self.extended_hours or not self.bracket_required:
            raise ValueError("Phase 15 v1 requires regular-hours protective bracket semantics")
        return self


class BrokerAccountSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_ACCOUNT_CONTRACT_VERSION
    broker: BrokerName
    environment: ExecutionEnvironment
    account_id: str = Field(min_length=1)
    as_of_utc: datetime
    equity: float = Field(ge=0.0)
    cash: float
    buying_power: float = Field(ge=0.0)
    gross_market_value: float = Field(ge=0.0)
    trading_blocked: bool = False
    shorting_enabled: bool | None = None

    @field_validator("as_of_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)


class BrokerPositionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_POSITION_SNAPSHOT_CONTRACT_VERSION
    broker: BrokerName
    account_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    quantity: float
    market_value: float
    average_entry_price: float | None = Field(default=None, gt=0.0)
    as_of_utc: datetime

    @field_validator("as_of_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)


class BrokerPreflightResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_PREFLIGHT_CONTRACT_VERSION
    broker: BrokerName
    intent_id: str = Field(min_length=16, max_length=128)
    accepted: bool
    as_of_utc: datetime
    estimated_cost: float | None = Field(default=None, ge=0.0)
    estimated_fees: float | None = Field(default=None, ge=0.0)
    provider_code: str | None = None
    provider_message: str | None = None
    reason_codes: tuple[str, ...]

    @field_validator("as_of_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_result(self) -> "BrokerPreflightResult":
        if not self.reason_codes:
            raise ValueError("broker preflight requires reason codes")
        return self


class BrokerOrderSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_ORDER_SNAPSHOT_CONTRACT_VERSION
    broker: BrokerName
    account_id: str = Field(min_length=1)
    client_order_id: str = Field(min_length=8, max_length=128)
    provider_order_id: str | None = None
    ticker: str = Field(min_length=1, max_length=64)
    side: BrokerOrderSide
    status: BrokerOrderStatus
    requested_quantity: float = Field(gt=0.0)
    filled_quantity: float = Field(ge=0.0)
    average_fill_price: float | None = Field(default=None, gt=0.0)
    submitted_at_utc: datetime | None = None
    updated_at_utc: datetime
    raw_status: str | None = None

    @field_validator("submitted_at_utc", "updated_at_utc")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_fill(self) -> "BrokerOrderSnapshot":
        if self.filled_quantity > self.requested_quantity + 1e-12:
            raise ValueError("filled quantity cannot exceed requested quantity")
        if self.filled_quantity > 0 and self.average_fill_price is None:
            raise ValueError("filled order requires average fill price")
        return self


class BrokerReconciliationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_RECONCILIATION_CONTRACT_VERSION
    broker: BrokerName
    environment: ExecutionEnvironment
    account: BrokerAccountSnapshot
    open_orders: tuple[BrokerOrderSnapshot, ...]
    positions: tuple[BrokerPositionSnapshot, ...]
    as_of_utc: datetime
    reconciled: bool
    zero_open_orders: bool
    zero_positions: bool
    safe_to_switch_broker: bool
    reason_codes: tuple[str, ...]

    @field_validator("as_of_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_reconciliation(self) -> "BrokerReconciliationSnapshot":
        if self.account.broker != self.broker or self.account.environment != self.environment:
            raise ValueError("reconciliation account identity differs from broker/environment")
        if self.zero_open_orders != (len(self.open_orders) == 0):
            raise ValueError("zero_open_orders flag does not match snapshot")
        if self.zero_positions != (len(self.positions) == 0):
            raise ValueError("zero_positions flag does not match snapshot")
        expected_switch = self.reconciled and self.zero_open_orders and self.zero_positions
        if self.safe_to_switch_broker != expected_switch:
            raise ValueError("safe_to_switch_broker flag does not match reconciliation state")
        if not self.reason_codes:
            raise ValueError("broker reconciliation requires reason codes")
        return self


class ExecutionOutcome(BaseModel):
    """Realized execution evidence only; never model/strategy authority."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = EXECUTION_OUTCOME_CONTRACT_VERSION
    intent_id: str = Field(min_length=16, max_length=128)
    broker: BrokerName
    environment: ExecutionEnvironment
    ticker: str = Field(min_length=1, max_length=64)
    direction: DiscoveryDirection
    quantity: float = Field(gt=0.0)
    entry_fill_price: float = Field(gt=0.0)
    exit_fill_price: float = Field(gt=0.0)
    opened_at_utc: datetime
    closed_at_utc: datetime
    exit_reason: ExecutionExitReason
    gross_pnl: float
    gross_return: float
    realized_r: float
    descriptive_only: bool = True
    can_promote_model: bool = False
    can_change_strategy_support: bool = False
    can_change_thresholds: bool = False

    @field_validator("opened_at_utc", "closed_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> "ExecutionOutcome":
        if self.closed_at_utc < self.opened_at_utc:
            raise ValueError("execution outcome cannot close before it opens")
        if not self.descriptive_only:
            raise ValueError("Phase 15 outcome learning must remain descriptive")
        if self.can_promote_model or self.can_change_strategy_support or self.can_change_thresholds:
            raise ValueError("Phase 15 outcome evidence cannot mutate model/strategy authority")
        return self
