from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.discovery_score import DiscoveryDirection


DEEP_RESEARCH_CASE_CONTRACT_VERSION = (
    "deep-research-case-v1-analogue-distribution-empirical-path-scenarios"
)


class AnalogueDistribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: int = Field(ge=0)
    unique_instruments: int = Field(ge=0)
    weighted_mean_return: float | None = None
    mean_return: float | None = None
    median_return: float | None = None
    positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    stddev_return: float | None = Field(default=None, ge=0.0)
    p05_return: float | None = None
    p10_return: float | None = None
    p25_return: float | None = None
    p75_return: float | None = None
    p90_return: float | None = None
    p95_return: float | None = None
    worst_return: float | None = None
    best_return: float | None = None


class AnalogueQuality(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = Field(min_length=1)
    analogue_count: int = Field(ge=0)
    unique_instruments: int = Field(ge=0)
    first_session_date: date | None = None
    last_session_date: date | None = None
    mean_distance: float | None = Field(default=None, ge=0.0)
    median_distance: float | None = Field(default=None, ge=0.0)
    p90_distance: float | None = Field(default=None, ge=0.0)
    path_rows: int = Field(ge=0)
    path_coverage: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[str, ...]

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(str(item).strip() for item in value if str(item).strip())
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("analogue quality reason codes must be unique")
        if not cleaned:
            raise ValueError("analogue quality requires at least one reason code")
        return cleaned


class ScenarioQuantiles(BaseModel):
    model_config = ConfigDict(frozen=True)

    p05: float
    p10: float
    p25: float
    median: float
    p75: float
    p90: float
    p95: float
    mean: float


class EmpiricalPathScenarios(BaseModel):
    model_config = ConfigDict(frozen=True)

    available: bool
    draw_count: int = Field(ge=0)
    seed: int = Field(ge=0)
    source_path_rows: int = Field(ge=0)
    session_1: ScenarioQuantiles | None = None
    session_2: ScenarioQuantiles | None = None
    session_3: ScenarioQuantiles | None = None
    max_adverse_excursion: ScenarioQuantiles | None = None
    max_favorable_excursion: ScenarioQuantiles | None = None
    terminal_positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_scenario_availability(self) -> "EmpiricalPathScenarios":
        payloads = (
            self.session_1,
            self.session_2,
            self.session_3,
            self.max_adverse_excursion,
            self.max_favorable_excursion,
        )
        if self.available:
            if self.draw_count <= 0 or self.source_path_rows <= 0 or any(item is None for item in payloads):
                raise ValueError("available empirical path scenarios require complete path evidence")
            if self.terminal_positive_rate is None:
                raise ValueError("available empirical path scenarios require terminal positive rate")
        return self


class DeepResearchCase(BaseModel):
    """Phase 12 research evidence only; never a trade or order instruction."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = DEEP_RESEARCH_CASE_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    direction: DiscoveryDirection
    market_state: str | None = None
    ticker_state: str | None = None
    phase11_candidate_sha256: str = Field(min_length=64, max_length=64)
    research_source_fingerprint: str = Field(min_length=64, max_length=64)
    similarity_feature_names: tuple[str, ...]
    current_feature_values: dict[str, float]
    eligible_pool_rows: int = Field(ge=0)
    analogue_distribution: AnalogueDistribution
    analogue_quality: AnalogueQuality
    scenarios: EmpiricalPathScenarios
    analogue_artifact_path: str = Field(min_length=1)
    analogue_artifact_sha256: str = Field(min_length=64, max_length=64)
    path_artifact_path: str = Field(min_length=1)
    path_artifact_sha256: str = Field(min_length=64, max_length=64)
    research_complete: bool
    reason_codes: tuple[str, ...]

    @field_validator("instrument_id", "ticker")
    @classmethod
    def clean_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("deep research identity cannot be blank")
        return cleaned

    @field_validator("similarity_feature_names", "reason_codes")
    @classmethod
    def unique_text(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(str(item).strip() for item in value if str(item).strip())
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("deep research text lists must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_research_semantics(self) -> "DeepResearchCase":
        if not self.similarity_feature_names:
            raise ValueError("deep research requires similarity features")
        if set(self.current_feature_values) != set(self.similarity_feature_names):
            raise ValueError("current feature values must exactly match similarity features")
        if not self.reason_codes:
            raise ValueError("deep research case requires reason codes")
        if self.research_complete and self.analogue_quality.status == "INSUFFICIENT":
            raise ValueError("insufficient analogue quality cannot be marked research complete")
        return self
