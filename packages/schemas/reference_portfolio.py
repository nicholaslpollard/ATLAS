from __future__ import annotations

import math
from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import ResearchStrategyFamily, ReferenceExitReason


REFERENCE_PORTFOLIO_DECISION_CONTRACT_VERSION = (
    "reference-portfolio-decision-v1-auditable-candidate-admission"
)
REFERENCE_SIMULATED_ORDER_CONTRACT_VERSION = (
    "reference-simulated-order-v1-research-replay-no-broker-authority"
)
REFERENCE_PORTFOLIO_OUTCOME_CONTRACT_VERSION = (
    "reference-portfolio-outcome-v1-cash-and-cost-reconciled"
)
REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION = (
    "reference-portfolio-replay-v1-cash-position-equity-and-rejections"
)


class ReferencePortfolioDecisionStatus(StrEnum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    REJECTED = "REJECTED"
    ADMITTED = "ADMITTED"


class ReferenceSimulatedOrderKind(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class ReferenceSimulatedOrderTiming(StrEnum):
    REGULAR_OPEN = "REGULAR_OPEN"
    INTRADAY_DAILY_BAR = "INTRADAY_DAILY_BAR"


class ReferencePortfolioDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = REFERENCE_PORTFOLIO_DECISION_CONTRACT_VERSION
    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    opportunity_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_id: str = Field(min_length=1)
    family: ResearchStrategyFamily
    direction: StrategyDirection
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    signal_session: date
    requested_entry_session: date | None
    status: ReferencePortfolioDecisionStatus
    reason_codes: tuple[str, ...]
    admitted_quantity: int | None = Field(default=None, ge=1)
    entry_price: float | None = Field(default=None, gt=0.0)
    initial_stop_price: float | None = Field(default=None, gt=0.0)
    target_price: float | None = Field(default=None, gt=0.0)
    sizing_equity: float | None = Field(default=None, gt=0.0)
    risk_budget: float | None = Field(default=None, gt=0.0)
    effective_risk_per_share: float | None = Field(default=None, gt=0.0)
    admitted_notional: float | None = Field(default=None, gt=0.0)

    @field_validator("reason_codes")
    @classmethod
    def valid_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("portfolio decision reason codes must be nonempty and unique")
        return cleaned

    @model_validator(mode="after")
    def admitted_fields_are_atomic(self) -> Self:
        fields = (
            self.admitted_quantity,
            self.entry_price,
            self.initial_stop_price,
            self.sizing_equity,
            self.risk_budget,
            self.effective_risk_per_share,
            self.admitted_notional,
        )
        if self.status == ReferencePortfolioDecisionStatus.ADMITTED:
            if self.requested_entry_session is None or any(value is None for value in fields):
                raise ValueError("admitted portfolio decision requires complete sizing geometry")
        elif any(value is not None for value in fields):
            raise ValueError("non-admitted portfolio decision cannot contain admission fields")
        return self


class ReferenceSimulatedOrderEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = REFERENCE_SIMULATED_ORDER_CONTRACT_VERSION
    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    opportunity_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_id: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    kind: ReferenceSimulatedOrderKind
    timing: ReferenceSimulatedOrderTiming
    session: date
    quantity: int = Field(ge=1)
    price: float = Field(gt=0.0)
    gross_notional: float = Field(gt=0.0)
    transaction_cost: float = Field(ge=0.0)
    cash_after: float = Field(ge=0.0)
    broker_order_created: bool = False
    paper_order_submitted: bool = False
    live_order_submitted: bool = False

    @model_validator(mode="after")
    def no_execution_authority(self) -> Self:
        if self.broker_order_created or self.paper_order_submitted or self.live_order_submitted:
            raise ValueError("reference simulated order cannot carry execution authority")
        return self


class ReferencePortfolioPositionOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = REFERENCE_PORTFOLIO_OUTCOME_CONTRACT_VERSION
    opportunity_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_id: str = Field(min_length=1)
    family: ResearchStrategyFamily
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    direction: StrategyDirection
    entry_session: date
    exit_session: date
    quantity: int = Field(ge=1)
    entry_price: float = Field(gt=0.0)
    exit_price: float = Field(gt=0.0)
    exit_reason: ReferenceExitReason
    entry_transaction_cost: float = Field(ge=0.0)
    exit_transaction_cost: float = Field(ge=0.0)
    gross_pnl: float
    net_pnl: float
    net_return_on_entry_notional: float
    holding_sessions: int = Field(ge=1)

    @field_validator("gross_pnl", "net_pnl", "net_return_on_entry_notional")
    @classmethod
    def finite_metrics(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("portfolio outcome metrics must be finite")
        return value


class ReferencePortfolioEquityPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    session: date
    cash: float = Field(ge=0.0)
    market_value: float = Field(ge=0.0)
    equity: float = Field(ge=0.0)
    gross_exposure_fraction: float = Field(ge=0.0)
    open_positions: int = Field(ge=0)
    peak_equity: float = Field(ge=0.0)
    drawdown: float = Field(le=0.0)


class ReferencePortfolioReplay(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION
    replay_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    independent_run_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    portfolio_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_equity: float = Field(gt=0.0)
    final_equity: float = Field(ge=0.0)
    total_return: float
    maximum_drawdown: float = Field(le=0.0)
    signals_fired: int = Field(ge=0)
    upstream_independent_candidates: int = Field(ge=0)
    admitted_positions: int = Field(ge=0)
    completed_positions: int = Field(ge=0)
    open_positions_at_end: int = Field(default=0, ge=0, le=0)
    winning_positions: int = Field(ge=0)
    losing_positions: int = Field(ge=0)
    win_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    profit_factor: float | None = Field(default=None, ge=0.0)
    total_transaction_cost: float = Field(ge=0.0)
    decisions: tuple[ReferencePortfolioDecision, ...]
    simulated_orders: tuple[ReferenceSimulatedOrderEvent, ...]
    position_outcomes: tuple[ReferencePortfolioPositionOutcome, ...]
    equity_curve: tuple[ReferencePortfolioEquityPoint, ...]
    summary_by_strategy: dict[str, dict[str, int | float | None]]
    summary_by_family: dict[str, dict[str, int | float | None]]
    replay_scope: str = "RESEARCH_ACCOUNT_REPLAY_NOT_QUALIFYING_HISTORICAL_OR_PAPER"
    selector_is_learned: bool = False
    short_borrow_modeled: bool = False
    correlation_model_available: bool = False
    sector_model_available: bool = False
    authority_promotion: bool = False
    protected_master_return_rows_read: int = Field(default=0, ge=0, le=0)
    provider_writes: int = Field(default=0, ge=0, le=0)
    broker_writes: int = Field(default=0, ge=0, le=0)
    paper_submits: int = Field(default=0, ge=0, le=0)
    live_writes: int = Field(default=0, ge=0, le=0)

    @field_validator("total_return")
    @classmethod
    def finite_total_return(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("portfolio total return must be finite")
        return value

    @model_validator(mode="after")
    def reconciles_counts_and_authority(self) -> Self:
        admitted = sum(
            item.status == ReferencePortfolioDecisionStatus.ADMITTED for item in self.decisions
        )
        if admitted != self.admitted_positions or len(self.position_outcomes) != self.completed_positions:
            raise ValueError("portfolio replay counts do not reconcile")
        if len(self.simulated_orders) != 2 * self.completed_positions:
            raise ValueError("resolved long-only replay requires one entry and one exit event")
        if self.open_positions_at_end != 0:
            raise ValueError("v1 rejects unresolved exits and must finish flat")
        if self.selector_is_learned or self.short_borrow_modeled or self.authority_promotion:
            raise ValueError("v1 replay cannot imply learned selection, short borrow, or promotion")
        return self
