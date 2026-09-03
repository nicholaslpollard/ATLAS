from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.strategy import StrategyDirection


STRATEGY_LAB_CONTRACT_VERSION = "a33-strategy-lab-v1-pre-outcome-reference-library"
DEFAULT_SIGNAL_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)


class StrategyEvidenceSource(StrEnum):
    PRACTITIONER_BASELINE = "PRACTITIONER_BASELINE"
    LITERATURE_ANCHORED = "LITERATURE_ANCHORED"
    INTERNAL_CHALLENGER = "INTERNAL_CHALLENGER"


class StrategyAuthority(StrEnum):
    RESEARCH = "RESEARCH"
    CANDIDATE = "CANDIDATE"
    HISTORICALLY_VALIDATED = "HISTORICALLY_VALIDATED"
    PAPER_VALIDATED = "PAPER_VALIDATED"
    LIVE_ELIGIBLE = "LIVE_ELIGIBLE"


class StrategyExecutionMode(StrEnum):
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    OPERATIONAL_PAPER = "OPERATIONAL_PAPER"
    QUALIFYING_PAPER = "QUALIFYING_PAPER"
    LIVE = "LIVE"


class ResearchStrategyFamily(StrEnum):
    MOVING_AVERAGE_TREND = "moving_average_trend"
    TREND_CONTINUATION = "trend_continuation"
    PULLBACK_CONTINUATION = "pullback_continuation"
    MOMENTUM = "momentum"
    PRICE_BREAKOUT = "price_breakout"
    VOLATILITY_EXPANSION = "volatility_expansion"
    MEAN_REVERSION = "mean_reversion"
    EXHAUSTION_REVERSAL = "exhaustion_reversal"
    VOLUME_CONFIRMATION = "volume_confirmation"
    RELATIVE_STRENGTH = "relative_strength"
    GAP = "gap"
    OPENING_RANGE = "opening_range"
    PREMARKET = "premarket"
    SUPPORT_RESISTANCE = "support_resistance"
    COMPOSITE = "composite"
    REGIME_CONDITIONED = "regime_conditioned"
    PAIRS_SPREAD = "pairs_spread"
    EVENT_DRIVEN = "event_driven"
    CHART_PATTERN = "chart_pattern"


class StrategySpecification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = STRATEGY_LAB_CONTRACT_VERSION
    strategy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    family: ResearchStrategyFamily
    evidence_source: StrategyEvidenceSource
    authority: StrategyAuthority = StrategyAuthority.RESEARCH
    directions: tuple[StrategyDirection, ...] = Field(min_length=1)
    native_timeframe: str = Field(min_length=1)
    universe_contract: str = Field(min_length=1)
    signal_contract: str = Field(min_length=1)
    entry_contract: str = Field(min_length=1)
    exit_contract: str = Field(min_length=1)
    risk_contract: str = Field(min_length=1)
    cost_contract: str = Field(min_length=1)
    evaluation_contract: str = Field(min_length=1)
    required_features: tuple[str, ...] = ()
    pre_outcome_frozen: bool = True
    pre_outcome_blockers: tuple[str, ...] = ()
    outcome_access_permitted: bool = False
    governed_performance_accessed: bool = False

    @model_validator(mode="after")
    def _validate_pre_outcome_contract(self) -> "StrategySpecification":
        if len(set(self.directions)) != len(self.directions):
            raise ValueError("directions must be unique")
        if len(set(self.required_features)) != len(self.required_features):
            raise ValueError("required_features must be unique")
        if len(set(self.pre_outcome_blockers)) != len(self.pre_outcome_blockers):
            raise ValueError("pre_outcome_blockers must be unique")
        if self.outcome_access_permitted and self.pre_outcome_blockers:
            raise ValueError("outcome access cannot be permitted while pre-outcome blockers remain")
        if self.outcome_access_permitted and not self.pre_outcome_frozen:
            raise ValueError("outcome access requires a frozen specification")
        if self.governed_performance_accessed and not self.outcome_access_permitted:
            raise ValueError("governed performance cannot be accessed before outcome access is permitted")
        return self

    @property
    def registry_key(self) -> str:
        return f"{self.strategy_id}:{self.version}"


_AUTHORITY_ORDER = {
    StrategyAuthority.RESEARCH: 0,
    StrategyAuthority.CANDIDATE: 1,
    StrategyAuthority.HISTORICALLY_VALIDATED: 2,
    StrategyAuthority.PAPER_VALIDATED: 3,
    StrategyAuthority.LIVE_ELIGIBLE: 4,
}


def validate_authority_transition(
    current: StrategyAuthority,
    target: StrategyAuthority,
    *,
    evidence_id: str | None,
) -> None:
    if current == target:
        return
    if _AUTHORITY_ORDER[target] != _AUTHORITY_ORDER[current] + 1:
        raise ValueError("strategy authority transitions must advance exactly one stage")
    if not evidence_id or not evidence_id.strip():
        raise ValueError("strategy authority promotion requires an explicit evidence_id")


def execution_mode_permitted(
    authority: StrategyAuthority,
    mode: StrategyExecutionMode,
) -> bool:
    if mode in {StrategyExecutionMode.HISTORICAL_REPLAY, StrategyExecutionMode.OPERATIONAL_PAPER}:
        return True
    if mode == StrategyExecutionMode.QUALIFYING_PAPER:
        return _AUTHORITY_ORDER[authority] >= _AUTHORITY_ORDER[StrategyAuthority.HISTORICALLY_VALIDATED]
    if mode == StrategyExecutionMode.LIVE:
        return authority == StrategyAuthority.LIVE_ELIGIBLE
    return False
