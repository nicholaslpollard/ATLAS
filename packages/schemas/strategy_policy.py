from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import (
    ResearchStrategyFamily,
    StrategyAuthority,
    StrategyEvidenceSource,
)


STRATEGY_POLICY_CONTRACT_VERSION = (
    "strategy-policy-v1-complete-versioned-daily-reference-no-trading-authority"
)
STRATEGY_AUTHORITY_CONTRACT_VERSION = (
    "strategy-authority-v1-separate-replay-operational-paper-qualifying-paper-live"
)


class StrategyExecutionEnvironment(StrEnum):
    RESEARCH_REPLAY = "RESEARCH_REPLAY"
    OPERATIONAL_PAPER = "OPERATIONAL_PAPER"
    QUALIFYING_PAPER = "QUALIFYING_PAPER"
    LIVE = "LIVE"


class StrategyTimeframe(StrEnum):
    DAILY = "1d"


class SignalRule(StrEnum):
    SMA_CROSS_UP = "SMA_CROSS_UP"
    EMA_PULLBACK_RECOVERY_LONG = "EMA_PULLBACK_RECOVERY_LONG"
    MACD_SIGNAL_CROSS_UP_BELOW_ZERO = "MACD_SIGNAL_CROSS_UP_BELOW_ZERO"
    MACD_SIGNAL_CROSS_DOWN_ABOVE_ZERO = "MACD_SIGNAL_CROSS_DOWN_ABOVE_ZERO"
    RSI_RECOVERY_LONG_TREND = "RSI_RECOVERY_LONG_TREND"
    DONCHIAN_VOLUME_BREAKOUT_LONG = "DONCHIAN_VOLUME_BREAKOUT_LONG"
    DONCHIAN_VOLUME_BREAKOUT_SHORT = "DONCHIAN_VOLUME_BREAKOUT_SHORT"
    BOLLINGER_SQUEEZE_BREAKOUT_LONG = "BOLLINGER_SQUEEZE_BREAKOUT_LONG"
    BOLLINGER_SQUEEZE_BREAKOUT_SHORT = "BOLLINGER_SQUEEZE_BREAKOUT_SHORT"


class EntryTiming(StrEnum):
    NEXT_REGULAR_SESSION_OPEN = "NEXT_REGULAR_SESSION_OPEN"


class IndicatorExitTiming(StrEnum):
    NEXT_REGULAR_SESSION_OPEN = "NEXT_REGULAR_SESSION_OPEN"


class SameBarCollisionPolicy(StrEnum):
    ADVERSE_FIRST = "ADVERSE_FIRST"


class InitialStopRule(StrEnum):
    ATR_FROM_ENTRY = "ATR_FROM_ENTRY"
    PULLBACK_LOW_OR_ATR_FARTHER = "PULLBACK_LOW_OR_ATR_FARTHER"
    DONCHIAN_BOUNDARY_OR_ATR_CLOSER = "DONCHIAN_BOUNDARY_OR_ATR_CLOSER"
    BOLLINGER_MID_OR_ATR_CLOSER = "BOLLINGER_MID_OR_ATR_CLOSER"


class IndicatorExitRule(StrEnum):
    NONE = "NONE"
    SMA_REVERSE_CROSS = "SMA_REVERSE_CROSS"
    CLOSE_BELOW_EMA_50 = "CLOSE_BELOW_EMA_50"
    MACD_OPPOSITE_CROSS = "MACD_OPPOSITE_CROSS"
    RSI_60_OR_EMA_20 = "RSI_60_OR_EMA_20"


class StrategyParameter(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    value: bool | int | float | str

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("parameter name cannot be blank")
        return cleaned

    @field_validator("value")
    @classmethod
    def finite_numeric_value(cls, value: bool | int | float | str) -> bool | int | float | str:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric strategy parameters must be finite")
        if isinstance(value, str) and not value.strip():
            raise ValueError("string strategy parameters cannot be blank")
        return value


class StrategyUniversePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_security_types: tuple[str, ...] = ("CS",)
    require_pit_active: bool = True
    require_clear_identity: bool = True
    minimum_close: float = Field(default=5.0, gt=0.0)
    prior_liquidity_lookback_sessions: int = Field(default=20, ge=1)
    minimum_prior_median_dollar_volume: float = Field(default=5_000_000.0, gt=0.0)
    adjusted_analytical_bars_with_raw_lineage: bool = True

    @field_validator("allowed_security_types")
    @classmethod
    def validate_security_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip().upper() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("allowed security types must be nonempty and unique")
        return cleaned


class StrategySignalPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule: SignalRule
    trigger_feature: str = Field(min_length=1)
    required_features: tuple[str, ...]
    minimum_history_sessions: int = Field(ge=2)
    parameters: tuple[StrategyParameter, ...]

    @field_validator("trigger_feature")
    @classmethod
    def clean_trigger(cls, value: str) -> str:
        return value.strip()

    @field_validator("required_features")
    @classmethod
    def validate_required_features(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("required features must be nonempty and unique")
        return cleaned

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: tuple[StrategyParameter, ...]) -> tuple[StrategyParameter, ...]:
        names = tuple(item.name for item in value)
        if not names or len(names) != len(set(names)):
            raise ValueError("strategy parameters must be nonempty and uniquely named")
        return value

    @model_validator(mode="after")
    def trigger_is_required(self) -> Self:
        if self.trigger_feature not in self.required_features:
            raise ValueError("trigger feature must be included in required_features")
        return self


class StrategyExecutionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_observation: str = "FINALIZED_DAILY_CLOSE"
    entry_timing: EntryTiming = EntryTiming.NEXT_REGULAR_SESSION_OPEN
    indicator_exit_timing: IndicatorExitTiming = IndicatorExitTiming.NEXT_REGULAR_SESSION_OPEN
    collision_policy: SameBarCollisionPolicy = SameBarCollisionPolicy.ADVERSE_FIRST
    trailing_stop_updates_after_close_for_next_session: bool = True
    broker_writes: int = Field(default=0, ge=0, le=0)
    paper_submits: int = Field(default=0, ge=0, le=0)
    live_writes: int = Field(default=0, ge=0, le=0)


class StrategyExitPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial_stop_rule: InitialStopRule
    initial_atr_multiple: float = Field(gt=0.0)
    profit_target_r: float | None = Field(default=None, gt=0.0)
    trailing_atr_multiple: float | None = Field(default=None, gt=0.0)
    indicator_exit_rule: IndicatorExitRule = IndicatorExitRule.NONE
    maximum_holding_sessions: int = Field(ge=1)


class StrategyRiskPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference_equity: float = Field(default=100_000.0, gt=0.0)
    account_risk_fraction: float = Field(default=0.0025, gt=0.0, le=0.01)
    maximum_position_fraction: float = Field(default=0.10, gt=0.0, le=1.0)
    maximum_initial_stop_fraction: float = Field(default=0.10, gt=0.0, le=0.50)
    integer_shares: bool = True
    minimum_quantity: int = Field(default=1, ge=1)


class StrategyCostPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    round_trip_cost_grid_bps: tuple[float, ...] = (0.0, 5.0, 10.0, 25.0, 50.0)
    primary_cost_bps: float = 10.0
    stress_cost_bps: float = 25.0
    generic_signal_costs_are_not_execution_model: bool = True

    @field_validator("round_trip_cost_grid_bps")
    @classmethod
    def validate_cost_grid(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        cleaned = tuple(float(item) for item in value)
        if not cleaned or any(not math.isfinite(item) or item < 0.0 for item in cleaned):
            raise ValueError("cost grid must contain finite non-negative values")
        if tuple(sorted(set(cleaned))) != cleaned:
            raise ValueError("cost grid must be unique and increasing")
        return cleaned

    @model_validator(mode="after")
    def primary_and_stress_are_in_grid(self) -> Self:
        if self.primary_cost_bps not in self.round_trip_cost_grid_bps:
            raise ValueError("primary cost must be in the cost grid")
        if self.stress_cost_bps not in self.round_trip_cost_grid_bps:
            raise ValueError("stress cost must be in the cost grid")
        if self.stress_cost_bps < self.primary_cost_bps:
            raise ValueError("stress cost cannot be below primary cost")
        return self


class StrategySpecification(BaseModel):
    """Complete immutable research policy; current execution authority is separate."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = STRATEGY_POLICY_CONTRACT_VERSION
    strategy_id: str = Field(pattern=r"^[a-z0-9_]+_v[1-9][0-9]*$")
    family_id: str = Field(pattern=r"^[a-z0-9_]+$")
    family: ResearchStrategyFamily
    direction: StrategyDirection
    timeframe: StrategyTimeframe = StrategyTimeframe.DAILY
    evidence_source: StrategyEvidenceSource = StrategyEvidenceSource.PRACTITIONER_BASELINE
    source_labels: tuple[str, ...]
    hypothesis: str = Field(min_length=1)
    signal: StrategySignalPolicy
    universe: StrategyUniversePolicy
    execution: StrategyExecutionPolicy
    exit: StrategyExitPolicy
    risk: StrategyRiskPolicy
    costs: StrategyCostPolicy
    invalidation_conditions: tuple[str, ...]
    limitations: tuple[str, ...]

    @field_validator("source_labels", "invalidation_conditions", "limitations")
    @classmethod
    def validate_text_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("strategy text tuples must be nonempty and unique")
        return cleaned

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


_AUTHORITY_ORDER = {
    StrategyAuthority.RESEARCH: 0,
    StrategyAuthority.CANDIDATE: 1,
    StrategyAuthority.HISTORICALLY_VALIDATED: 2,
    StrategyAuthority.PAPER_VALIDATED: 3,
    StrategyAuthority.LIVE_ELIGIBLE: 4,
}


class StrategyAuthorityRecord(BaseModel):
    """Version-bound permission record; ranking or performance cannot bypass it."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = STRATEGY_AUTHORITY_CONTRACT_VERSION
    strategy_id: str = Field(min_length=1)
    strategy_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: StrategyAuthority
    allowed_environments: tuple[StrategyExecutionEnvironment, ...]
    evidence_references: tuple[str, ...]
    operational_paper_is_qualifying: bool = False
    explicit_live_operator_enable: bool = False

    @field_validator("allowed_environments")
    @classmethod
    def unique_environments(
        cls, value: tuple[StrategyExecutionEnvironment, ...]
    ) -> tuple[StrategyExecutionEnvironment, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("allowed environments must be nonempty and unique")
        return value

    @field_validator("evidence_references")
    @classmethod
    def clean_evidence_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("authority evidence references must be nonempty and unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_authority_boundaries(self) -> Self:
        environments = set(self.allowed_environments)
        if StrategyExecutionEnvironment.QUALIFYING_PAPER in environments:
            if _AUTHORITY_ORDER[self.authority] < _AUTHORITY_ORDER[StrategyAuthority.HISTORICALLY_VALIDATED]:
                raise ValueError("qualifying PAPER requires historical validation")
        if StrategyExecutionEnvironment.LIVE in environments:
            if self.authority != StrategyAuthority.LIVE_ELIGIBLE:
                raise ValueError("LIVE permission requires LIVE_ELIGIBLE authority")
            if not self.explicit_live_operator_enable:
                raise ValueError("LIVE permission requires explicit operator enable")
        elif self.explicit_live_operator_enable:
            raise ValueError("explicit LIVE enable is invalid without LIVE permission")
        if self.operational_paper_is_qualifying:
            raise ValueError("operational PAPER can never be marked as qualifying PAPER")
        return self
