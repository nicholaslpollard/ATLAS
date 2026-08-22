from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState
from packages.schemas.strategy import MLProbabilityEvidence, StrategyAssessment, StrategyRouteDecision


CANDIDATE_PROMOTION_CONTRACT_VERSION = (
    "candidate-promotion-v1-discovery-supported-strategy-regime-ml-context"
)


class StrategyHistoricalSupportSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    eligible_for_candidate_promotion: bool
    primary_cost_bps: float = Field(ge=0.0)
    development_mean_return: float | None = None
    first_half_mean_return: float | None = None
    second_half_mean_return: float | None = None
    development_rows: int = Field(ge=0)


class CandidatePromotionRecord(BaseModel):
    """Phase 11 promoted/rejected case before trade construction."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = CANDIDATE_PROMOTION_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    discovery_effective_state: DiscoveryState
    discovery_direction: DiscoveryDirection
    discovery_priority_score: float = Field(ge=0.0, le=1.0)
    market_state: str | None = None
    sector_state: str | None = None
    ticker_state: str | None = None
    ml_probability_evidence: MLProbabilityEvidence
    historical_support: tuple[StrategyHistoricalSupportSnapshot, ...]
    route_decisions: tuple[StrategyRouteDecision, ...]
    strategy_assessments: tuple[StrategyAssessment, ...]
    supported_fired_strategy_ids: tuple[str, ...]
    promoted: bool
    reason_codes: tuple[str, ...]

    @field_validator("instrument_id", "ticker")
    @classmethod
    def strip_promotion_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("candidate identity text cannot be blank")
        return cleaned

    @field_validator("supported_fired_strategy_ids", "reason_codes")
    @classmethod
    def unique_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(str(item).strip() for item in value if str(item).strip())
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("candidate evidence lists must not contain duplicates")
        return cleaned

    @model_validator(mode="after")
    def validate_promotion_semantics(self) -> "CandidatePromotionRecord":
        if not self.reason_codes:
            raise ValueError("candidate decision requires reason codes")
        if self.promoted:
            if self.discovery_effective_state not in {DiscoveryState.WARM, DiscoveryState.HOT}:
                raise ValueError("promoted candidate must be WARM or HOT")
            if self.discovery_direction == DiscoveryDirection.NEUTRAL:
                raise ValueError("promoted candidate cannot have neutral discovery direction")
            if not self.supported_fired_strategy_ids:
                raise ValueError("promoted candidate requires a historically supported fired strategy")
        return self
