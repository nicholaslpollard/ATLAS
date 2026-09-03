from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


STRATEGY_EVIDENCE_CONTRACT_VERSION = "strategy-evidence-v1-regime-routed-no-execution"
STRATEGY_ROUTE_CONTRACT_VERSION = "strategy-route-v1-external-deterministic-regime-routing"


class StrategyDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class StrategyFamily(StrEnum):
    TREND_FOLLOWING = "trend_following"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    PULLBACK = "pullback"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY_BREAKOUT = "volatility_breakout"


class StrategyRegimeFit(StrEnum):
    PREFERRED = "preferred"
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class MLProbabilityEvidence(BaseModel):
    """Accepted three-class probability evidence carried beside strategy evidence.

    The probability vector is context only. This schema intentionally contains no
    argmax-to-trade conversion and no threshold that can turn ML into a trade signal.
    """

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    p_down: float = Field(ge=0.0, le=1.0)
    p_neutral: float = Field(ge=0.0, le=1.0)
    p_up: float = Field(ge=0.0, le=1.0)

    @field_validator("model_id")
    @classmethod
    def clean_model_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("model_id cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_probability_sum(self) -> "MLProbabilityEvidence":
        total = self.p_down + self.p_neutral + self.p_up
        if abs(total - 1.0) > 1e-6:
            raise ValueError("ML probabilities must sum to one")
        return self


class StrategyAssessment(BaseModel):
    """Deterministic setup evidence from one strategy implementation.

    `fired` means the strategy's setup conditions are present. It is not an order,
    position, trade geometry, portfolio decision, or broker instruction.
    """

    model_config = ConfigDict(frozen=True)

    contract_version: str = STRATEGY_EVIDENCE_CONTRACT_VERSION
    strategy_id: str = Field(min_length=1)
    family: StrategyFamily
    direction: StrategyDirection
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    fired: bool
    conditions_met: int = Field(ge=0)
    condition_count: int = Field(ge=1)
    evidence_score: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any]
    reason_codes: tuple[str, ...]
    ml_probability_evidence: MLProbabilityEvidence | None = None

    @field_validator("strategy_id", "instrument_id", "ticker")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required strategy text cannot be blank")
        return cleaned

    @field_validator("reason_codes")
    @classmethod
    def require_unique_reason_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(str(item).strip() for item in value if str(item).strip())
        if not cleaned:
            raise ValueError("strategy assessment requires at least one reason code")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("strategy reason codes must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_evidence_semantics(self) -> "StrategyAssessment":
        if self.conditions_met > self.condition_count:
            raise ValueError("conditions_met cannot exceed condition_count")
        expected = self.conditions_met / self.condition_count
        if abs(self.evidence_score - expected) > 1e-12:
            raise ValueError("evidence_score must equal conditions_met / condition_count")
        if self.fired != (self.conditions_met == self.condition_count):
            raise ValueError("fired must mean every locked strategy condition is met")
        return self


class StrategyRouteDecision(BaseModel):
    """External router decision for one strategy/candidate pair."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = STRATEGY_ROUTE_CONTRACT_VERSION
    strategy_id: str = Field(min_length=1)
    family: StrategyFamily
    direction: StrategyDirection
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    eligible: bool
    direction_match: bool
    market_fit: StrategyRegimeFit
    sector_fit: StrategyRegimeFit
    ticker_fit: StrategyRegimeFit
    market_state: str | None = None
    sector_state: str | None = None
    ticker_state: str | None = None
    reason_codes: tuple[str, ...]

    @field_validator("strategy_id", "instrument_id", "ticker")
    @classmethod
    def clean_route_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required route text cannot be blank")
        return cleaned

    @field_validator("reason_codes")
    @classmethod
    def require_route_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(str(item).strip() for item in value if str(item).strip())
        if not cleaned:
            raise ValueError("route decision requires at least one reason code")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("route reason codes must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_route_semantics(self) -> "StrategyRouteDecision":
        blocked = StrategyRegimeFit.BLOCKED in {self.market_fit, self.sector_fit, self.ticker_fit}
        if self.eligible and (not self.direction_match or blocked):
            raise ValueError("eligible route cannot contradict direction or a blocked regime")
        return self
