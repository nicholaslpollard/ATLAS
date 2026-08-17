from __future__ import annotations

from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState


DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION = (
    "discovery-state-snapshot-v1-hysteresis-and-score-lineage"
)


class DiscoveryStateRecord(BaseModel):
    """Persisted Phase 8 discovery state after deterministic hysteresis."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    raw_state: DiscoveryState
    effective_state: DiscoveryState
    previous_effective_state: DiscoveryState | None = None
    warm_confirmation_streak: int = Field(ge=0)
    demotion_streak: int = Field(ge=0)
    transition: str = Field(min_length=1)
    priority_score: float = Field(ge=0.0, le=1.0)
    bull_evidence: float = Field(ge=0.0, le=1.0)
    bear_evidence: float = Field(ge=0.0, le=1.0)
    direction: DiscoveryDirection
    scored_timeframes: int = Field(ge=0, le=3)
    top_setup: str = Field(min_length=1)

    @field_validator("instrument_id", "ticker", "transition", "top_setup")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("required discovery state text cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_state_semantics(self) -> "DiscoveryStateRecord":
        if self.raw_state == DiscoveryState.HOT and self.scored_timeframes < 3:
            raise ValueError("raw HOT state requires three scored timeframes")
        if self.effective_state == DiscoveryState.HOT and self.scored_timeframes < 3:
            raise ValueError("effective HOT state requires three scored timeframes")
        if self.previous_effective_state is None and not self.transition.startswith("bootstrap"):
            raise ValueError("state without previous observation must use a bootstrap transition")
        return self
