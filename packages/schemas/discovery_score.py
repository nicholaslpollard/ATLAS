from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.candidate import DiscoveryActivityTier
from packages.schemas.universe import UniverseRoute


DISCOVERY_SCORE_CONTRACT_VERSION = "discovery-score-v1-vectorized-multitimeframe-evidence"


class DiscoveryDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class DiscoveryState(StrEnum):
    NORMAL = "normal"
    WATCH = "watch"
    WARM = "warm"
    HOT = "hot"


class DiscoveryScoreRecord(BaseModel):
    """Vectorized Phase 8 setup/evidence score for one routed instrument."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = DISCOVERY_SCORE_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    security_type: str | None = None
    routes: tuple[UniverseRoute, ...]
    activity_tier: DiscoveryActivityTier
    broad_discovery_ready: bool
    mandatory_route: bool

    has_1d_score_input: bool
    has_regular_4h_score_input: bool
    has_regular_1h_score_input: bool
    scored_timeframes: int = Field(ge=0, le=3)

    trend_score: float = Field(ge=0.0, le=1.0)
    momentum_score: float = Field(ge=0.0, le=1.0)
    breakout_score: float = Field(ge=0.0, le=1.0)
    pullback_score: float = Field(ge=0.0, le=1.0)
    reversal_score: float = Field(ge=0.0, le=1.0)
    mean_reversion_score: float = Field(ge=0.0, le=1.0)
    relative_strength_score: float = Field(ge=0.0, le=1.0)
    unusual_volume_score: float = Field(ge=0.0, le=1.0)
    volatility_expansion_score: float = Field(ge=0.0, le=1.0)
    breakdown_score: float = Field(ge=0.0, le=1.0)

    bull_evidence: float = Field(ge=0.0, le=1.0)
    bear_evidence: float = Field(ge=0.0, le=1.0)
    priority_score: float = Field(ge=0.0, le=1.0)
    top_setup: str = Field(min_length=1)
    direction: DiscoveryDirection
    raw_state: DiscoveryState

    @field_validator("instrument_id", "ticker", "top_setup")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("required discovery score text cannot be blank")
        return cleaned

    @field_validator("routes")
    @classmethod
    def unique_routes(cls, value: tuple[UniverseRoute, ...]) -> tuple[UniverseRoute, ...]:
        if not value:
            raise ValueError("discovery score requires at least one route")
        if len(value) != len(set(value)):
            raise ValueError("discovery score routes must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def validate_score_semantics(self) -> "DiscoveryScoreRecord":
        expected = sum(
            (
                self.has_1d_score_input,
                self.has_regular_4h_score_input,
                self.has_regular_1h_score_input,
            )
        )
        if self.scored_timeframes != expected:
            raise ValueError("scored_timeframes does not match timeframe availability")
        if not (self.broad_discovery_ready or self.mandatory_route):
            raise ValueError("score record must come from a consideration-required candidate")
        if self.direction == DiscoveryDirection.BULLISH and self.bull_evidence < self.bear_evidence:
            raise ValueError("bullish direction contradicts evidence ordering")
        if self.direction == DiscoveryDirection.BEARISH and self.bear_evidence < self.bull_evidence:
            raise ValueError("bearish direction contradicts evidence ordering")
        return self
