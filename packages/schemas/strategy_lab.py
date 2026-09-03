from __future__ import annotations

import math
from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.strategy import StrategyDirection, StrategyFamily


REFERENCE_OPPORTUNITY_CONTRACT_VERSION = (
    "reference-opportunity-v1-fired-rejected-selected-counterfactual-outcome"
)
REFERENCE_HISTORICAL_RUN_CONTRACT_VERSION = (
    "reference-historical-run-v1-independent-strategy-replay-no-protected-or-broker"
)


class OpportunityDisposition(StrEnum):
    UNIVERSE_REJECTED = "UNIVERSE_REJECTED"
    NO_NEXT_ENTRY_BAR = "NO_NEXT_ENTRY_BAR"
    RISK_REJECTED = "RISK_REJECTED"
    SELECTED_INDEPENDENT_REPLAY = "SELECTED_INDEPENDENT_REPLAY"
    NOT_SELECTED_ACTIVE_POSITION = "NOT_SELECTED_ACTIVE_POSITION"


class OpportunityOutcomeStatus(StrEnum):
    NOT_SIMULATED = "NOT_SIMULATED"
    EXITED = "EXITED"
    OPEN_UNRESOLVED = "OPEN_UNRESOLVED"


class ReferenceExitReason(StrEnum):
    INITIAL_OR_TRAILING_STOP = "INITIAL_OR_TRAILING_STOP"
    PROFIT_TARGET = "PROFIT_TARGET"
    SMA_REVERSE_CROSS = "SMA_REVERSE_CROSS"
    CLOSE_BELOW_EMA_50 = "CLOSE_BELOW_EMA_50"
    MACD_OPPOSITE_CROSS = "MACD_OPPOSITE_CROSS"
    RSI_60_OR_EMA_20 = "RSI_60_OR_EMA_20"
    MAXIMUM_HOLD = "MAXIMUM_HOLD"


class StrategyTrialStage(StrEnum):
    SPECIFICATION = "SPECIFICATION"
    SYNTHETIC_VALIDATION = "SYNTHETIC_VALIDATION"
    DEVELOPMENT_REPLAY = "DEVELOPMENT_REPLAY"
    WALK_FORWARD = "WALK_FORWARD"
    QUALIFYING_HISTORICAL = "QUALIFYING_HISTORICAL"


class StrategyTrialDisposition(StrEnum):
    REGISTERED = "REGISTERED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"


class StrategyTrialDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]+$")
    registered_at_utc: datetime
    stage: StrategyTrialStage
    disposition: StrategyTrialDisposition
    family_ids: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    strategy_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    hypotheses: tuple[str, ...]
    input_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    performance_outcomes_opened: bool = False
    master_protected_return_rows_read: int = Field(default=0, ge=0, le=0)
    notes: tuple[str, ...]

    @field_validator("family_ids", "strategy_ids", "hypotheses", "notes")
    @classmethod
    def clean_trial_tuples(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("trial tuples must be nonempty and unique")
        return cleaned

    @field_validator("registered_at_utc")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trial registration timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_trial_state(self) -> Self:
        if self.performance_outcomes_opened and self.input_fingerprint is None:
            raise ValueError("opened outcomes require a bound input fingerprint")
        if self.disposition == StrategyTrialDisposition.COMPLETED and self.stage in {
            StrategyTrialStage.DEVELOPMENT_REPLAY,
            StrategyTrialStage.WALK_FORWARD,
            StrategyTrialStage.QUALIFYING_HISTORICAL,
        }:
            if self.run_fingerprint is None:
                raise ValueError("completed replay trials require a run fingerprint")
        return self


class StrategyTrialRecord(StrategyTrialDraft):
    contract_version: str
    sequence: int = Field(ge=1)
    previous_record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReferenceOpportunityRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = REFERENCE_OPPORTUNITY_CONTRACT_VERSION
    opportunity_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_id: str = Field(min_length=1)
    strategy_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    family: StrategyFamily
    direction: StrategyDirection
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    signal_session: date
    signal_timestamp_utc: datetime
    market_regime: str
    sector_regime: str
    ticker_regime: str
    volatility_bucket: str
    liquidity_bucket: str
    signal_fired: bool = True
    universe_eligible: bool
    disposition: OpportunityDisposition
    reason_codes: tuple[str, ...]
    selected_for_independent_replay: bool
    counterfactual_only: bool
    entry_session: date | None = None
    entry_price: float | None = Field(default=None, gt=0.0)
    initial_stop_price: float | None = Field(default=None, gt=0.0)
    target_price: float | None = Field(default=None, gt=0.0)
    quantity: int | None = Field(default=None, ge=1)
    initial_risk_per_share: float | None = Field(default=None, gt=0.0)
    outcome_status: OpportunityOutcomeStatus = OpportunityOutcomeStatus.NOT_SIMULATED
    exit_session: date | None = None
    exit_price: float | None = Field(default=None, gt=0.0)
    exit_reason: ReferenceExitReason | None = None
    holding_sessions: int | None = Field(default=None, ge=1)
    exit_at_session_open: bool = False
    same_bar_collision_adverse_first: bool = False
    gross_directional_return: float | None = None
    net_directional_returns_by_cost_bps: dict[str, float] = Field(default_factory=dict)
    primary_net_directional_return: float | None = None
    risk_multiple: float | None = None
    maximum_favorable_excursion: float | None = None
    maximum_adverse_excursion: float | None = None

    @field_validator("instrument_id", "ticker", "strategy_id")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("opportunity text fields cannot be blank")
        return cleaned

    @field_validator("reason_codes")
    @classmethod
    def validate_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("opportunity reason codes must be nonempty and unique")
        return cleaned

    @field_validator(
        "gross_directional_return",
        "primary_net_directional_return",
        "risk_multiple",
        "maximum_favorable_excursion",
        "maximum_adverse_excursion",
    )
    @classmethod
    def finite_optional_metric(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("opportunity metrics must be finite")
        return value

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        planned = self.entry_session is not None
        plan_fields = (
            self.entry_price,
            self.initial_stop_price,
            self.quantity,
            self.initial_risk_per_share,
        )
        if planned != all(value is not None for value in plan_fields):
            raise ValueError("planned opportunity fields must be present together")
        if self.selected_for_independent_replay == self.counterfactual_only:
            raise ValueError("selected and counterfactual flags must be exact opposites")
        if self.disposition == OpportunityDisposition.SELECTED_INDEPENDENT_REPLAY:
            if not self.selected_for_independent_replay or not planned:
                raise ValueError("selected replay disposition requires a trade plan")
        elif self.selected_for_independent_replay:
            raise ValueError("only selected replay disposition can be selected")
        if self.outcome_status == OpportunityOutcomeStatus.EXITED:
            required = (
                self.exit_session,
                self.exit_price,
                self.exit_reason,
                self.holding_sessions,
                self.gross_directional_return,
                self.primary_net_directional_return,
                self.risk_multiple,
                self.maximum_favorable_excursion,
                self.maximum_adverse_excursion,
            )
            if any(value is None for value in required) or not self.net_directional_returns_by_cost_bps:
                raise ValueError("exited opportunity requires complete outcome fields")
        elif any(value is not None for value in (self.exit_session, self.exit_price, self.exit_reason)):
            raise ValueError("non-exited opportunity cannot contain an exit")
        elif self.exit_at_session_open:
            raise ValueError("non-exited opportunity cannot be marked as an open exit")
        if planned:
            if self.direction == StrategyDirection.LONG:
                if not float(self.initial_stop_price) < float(self.entry_price):
                    raise ValueError("LONG plan requires stop below entry")
                if self.target_price is not None and not float(self.target_price) > float(self.entry_price):
                    raise ValueError("LONG plan requires target above entry")
            else:
                if not float(self.initial_stop_price) > float(self.entry_price):
                    raise ValueError("SHORT plan requires stop above entry")
                if self.target_price is not None and not float(self.target_price) < float(self.entry_price):
                    raise ValueError("SHORT plan requires target below entry")
        return self


class ReferenceHistoricalRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = REFERENCE_HISTORICAL_RUN_CONTRACT_VERSION
    run_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_rows: int = Field(ge=0)
    input_instruments: int = Field(ge=0)
    first_session: date | None
    last_session: date | None
    opportunities: tuple[ReferenceOpportunityRecord, ...]
    summary_by_strategy: dict[str, dict[str, int | float | None]]
    condition_slices: dict[
        str, dict[str, dict[str, dict[str, int | float | None]]]
    ]
    replay_scope: str = "INDEPENDENT_STRATEGY_REPLAY_NOT_PORTFOLIO_SIMULATION"
    protected_master_return_rows_read: int = Field(default=0, ge=0, le=0)
    broker_writes: int = Field(default=0, ge=0, le=0)
    paper_submits: int = Field(default=0, ge=0, le=0)
    live_writes: int = Field(default=0, ge=0, le=0)
