from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.discovery_score import DiscoveryDirection


PHASE13_CASE_FILE_CONTRACT_VERSION = (
    "phase13-case-file-v1-context-instrument-geometry-broker-neutral-portfolio-risk"
)


class EvidenceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class InstrumentKind(StrEnum):
    EQUITY = "EQUITY"
    OPTION = "OPTION"


class GeometryStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class PortfolioRiskStatus(StrEnum):
    ADMISSIBLE = "ADMISSIBLE"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class NewsContextSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    availability: EvidenceAvailability
    cutoff_utc: datetime
    lookback_calendar_days: int = Field(ge=1)
    article_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    latest_published_utc: datetime | None = None
    provider_snapshot_path: str | None = None
    provider_snapshot_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> "NewsContextSummary":
        classified = self.positive_count + self.neutral_count + self.negative_count
        if classified > self.article_count:
            raise ValueError("classified news count cannot exceed article count")
        if self.availability == EvidenceAvailability.UNAVAILABLE:
            if self.article_count != 0 or self.sentiment_score is not None:
                raise ValueError("unavailable news context cannot carry article sentiment")
        if (self.provider_snapshot_path is None) != (self.provider_snapshot_sha256 is None):
            raise ValueError("news snapshot path/hash must be supplied together")
        if not self.reason_codes:
            raise ValueError("news context requires reason codes")
        return self


class OptionCandidateEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_ticker: str = Field(min_length=1)
    contract_type: str = Field(pattern="^(call|put)$")
    expiration_date: date
    dte: int = Field(ge=0)
    strike: float = Field(gt=0.0)
    bid: float = Field(ge=0.0)
    ask: float = Field(ge=0.0)
    mid: float = Field(gt=0.0)
    spread_to_mid: float = Field(ge=0.0)
    open_interest: int = Field(ge=0)
    volume: int | None = Field(default=None, ge=0)
    delta: float | None = Field(default=None, ge=-1.0, le=1.0)
    implied_volatility: float | None = Field(default=None, ge=0.0)
    eligible: bool
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_quote(self) -> "OptionCandidateEvidence":
        if self.ask < self.bid:
            raise ValueError("option ask cannot be below bid")
        expected_mid = (self.bid + self.ask) / 2.0
        if abs(expected_mid - self.mid) > max(1e-12, abs(expected_mid) * 1e-9):
            raise ValueError("option mid must equal bid/ask midpoint")
        if not self.reason_codes:
            raise ValueError("option candidate requires reason codes")
        return self


class InstrumentSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    primary_kind: InstrumentKind
    primary_ticker: str = Field(min_length=1)
    option_chain_availability: EvidenceAvailability
    option_chain_snapshot_path: str | None = None
    option_chain_snapshot_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    ranked_option_alternatives: tuple[OptionCandidateEvidence, ...] = ()
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_selection(self) -> "InstrumentSelection":
        if self.primary_kind != InstrumentKind.EQUITY:
            raise ValueError("Phase 13 v1 primary instrument must remain equity")
        if (self.option_chain_snapshot_path is None) != (self.option_chain_snapshot_sha256 is None):
            raise ValueError("option-chain snapshot path/hash must be supplied together")
        if self.option_chain_availability == EvidenceAvailability.UNAVAILABLE and self.ranked_option_alternatives:
            raise ValueError("unavailable option chain cannot carry ranked alternatives")
        if not self.reason_codes:
            raise ValueError("instrument selection requires reason codes")
        return self


class TradeGeometry(BaseModel):
    """Reference planning geometry only; never an assumed fill or executable order."""

    model_config = ConfigDict(frozen=True)

    status: GeometryStatus
    direction: DiscoveryDirection
    horizon_sessions: int = Field(ge=1)
    reference_entry: float | None = Field(default=None, gt=0.0)
    stop: float | None = Field(default=None, gt=0.0)
    target: float | None = Field(default=None, gt=0.0)
    risk_fraction: float | None = Field(default=None, gt=0.0)
    reward_fraction: float | None = Field(default=None, gt=0.0)
    reward_to_risk: float | None = Field(default=None, gt=0.0)
    natr_14: float | None = Field(default=None, gt=0.0)
    empirical_mae_p10: float | None = None
    empirical_mfe_p75: float | None = Field(default=None, gt=0.0)
    reference_only_not_fill: bool = True
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_geometry(self) -> "TradeGeometry":
        numeric = (
            self.reference_entry,
            self.stop,
            self.target,
            self.risk_fraction,
            self.reward_fraction,
            self.reward_to_risk,
            self.natr_14,
            self.empirical_mae_p10,
            self.empirical_mfe_p75,
        )
        if self.status == GeometryStatus.AVAILABLE:
            if any(value is None for value in numeric):
                raise ValueError("available geometry requires complete evidence")
            assert self.reference_entry is not None
            assert self.stop is not None
            assert self.target is not None
            assert self.risk_fraction is not None
            assert self.reward_fraction is not None
            assert self.reward_to_risk is not None
            if self.reward_fraction <= self.risk_fraction:
                raise ValueError("available geometry requires empirical reward > risk")
            expected_ratio = self.reward_fraction / self.risk_fraction
            if abs(expected_ratio - self.reward_to_risk) > max(1e-12, expected_ratio * 1e-9):
                raise ValueError("reward_to_risk does not match geometry fractions")
            if self.direction == DiscoveryDirection.BULLISH:
                if not self.stop < self.reference_entry < self.target:
                    raise ValueError("LONG geometry must satisfy stop < entry < target")
            elif self.direction == DiscoveryDirection.BEARISH:
                if not self.stop > self.reference_entry > self.target:
                    raise ValueError("SHORT geometry must satisfy stop > entry > target")
            else:
                raise ValueError("available Phase 13 geometry cannot be neutral")
        else:
            if any(value is not None for value in numeric):
                raise ValueError("unavailable geometry cannot carry partial numeric plan")
        if not self.reference_only_not_fill:
            raise ValueError("Phase 13 geometry must remain reference-only")
        if not self.reason_codes:
            raise ValueError("trade geometry requires reason codes")
        return self


class PortfolioPositionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    signed_market_value: float


class PortfolioSnapshot(BaseModel):
    """Broker-neutral input supplied by a future adapter or test harness."""

    model_config = ConfigDict(frozen=True)

    as_of_utc: datetime
    equity: float = Field(gt=0.0)
    cash: float
    gross_market_value: float = Field(ge=0.0)
    positions: tuple[PortfolioPositionEvidence, ...] = ()
    source: str = Field(min_length=1)
    source_fingerprint: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_positions(self) -> "PortfolioSnapshot":
        ids = [item.instrument_id for item in self.positions]
        if len(ids) != len(set(ids)):
            raise ValueError("portfolio snapshot contains duplicate instrument identities")
        return self


class PortfolioRiskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: PortfolioRiskStatus
    proposed_risk_budget: float | None = Field(default=None, gt=0.0)
    proposed_quantity: int | None = Field(default=None, ge=1)
    proposed_notional: float | None = Field(default=None, gt=0.0)
    projected_single_name_fraction: float | None = Field(default=None, ge=0.0)
    projected_gross_fraction: float | None = Field(default=None, ge=0.0)
    max_abs_correlation: float | None = Field(default=None, ge=0.0, le=1.0)
    open_positions_before: int | None = Field(default=None, ge=0)
    proposed_quantity_is_order: bool = False
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_risk(self) -> "PortfolioRiskAssessment":
        numeric = (
            self.proposed_risk_budget,
            self.proposed_quantity,
            self.proposed_notional,
            self.projected_single_name_fraction,
            self.projected_gross_fraction,
            self.open_positions_before,
        )
        if self.status == PortfolioRiskStatus.UNAVAILABLE:
            if any(value is not None for value in numeric) or self.max_abs_correlation is not None:
                raise ValueError("unavailable portfolio risk cannot carry proposed sizing")
        else:
            if any(value is None for value in numeric):
                raise ValueError("evaluated portfolio risk requires complete sizing evidence")
        if self.proposed_quantity_is_order:
            raise ValueError("Phase 13 proposed quantity can never be an order")
        if not self.reason_codes:
            raise ValueError("portfolio risk assessment requires reason codes")
        return self


class Phase13CaseFile(BaseModel):
    """Deterministic Phase 13 case plan for later independent AI audit."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = PHASE13_CASE_FILE_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    direction: DiscoveryDirection
    phase12_case_sha256: str = Field(min_length=64, max_length=64)
    phase12_research_complete: bool
    market_state: str | None = None
    ticker_state: str | None = None
    news_context: NewsContextSummary
    instrument_selection: InstrumentSelection
    geometry: TradeGeometry
    portfolio_risk: PortfolioRiskAssessment
    phase14_review_ready: bool
    reason_codes: tuple[str, ...]

    @field_validator("instrument_id", "ticker")
    @classmethod
    def clean_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Phase 13 identity cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_case(self) -> "Phase13CaseFile":
        if self.instrument_selection.primary_ticker != self.ticker:
            raise ValueError("primary equity ticker must match Phase 13 case ticker")
        if self.geometry.direction != self.direction:
            raise ValueError("Phase 13 geometry direction changed")
        expected_ready = (
            self.phase12_research_complete
            and self.geometry.status == GeometryStatus.AVAILABLE
            and self.portfolio_risk.status == PortfolioRiskStatus.ADMISSIBLE
        )
        if self.phase14_review_ready != expected_ready:
            raise ValueError("Phase 14 review-ready flag does not match deterministic prerequisites")
        if not self.reason_codes:
            raise ValueError("Phase 13 case requires reason codes")
        return self
