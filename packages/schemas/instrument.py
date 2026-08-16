from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.core.enums import DataProvider, InstrumentIdentityQuality
from packages.core.timestamps import to_utc


class InstrumentReferenceObservation(BaseModel):
    model_config = ConfigDict(frozen=True)
    instrument_id: str = Field(min_length=1)
    identity_key: str = Field(min_length=1)
    identity_quality: InstrumentIdentityQuality
    provider: DataProvider = DataProvider.MASSIVE
    as_of_date: date
    ticker: str = Field(min_length=1, max_length=64)
    name: str | None = None
    market: str | None = None
    locale: str | None = None
    currency_name: str | None = None
    primary_exchange: str | None = None
    security_type: str | None = None
    active: bool = True
    composite_figi: str | None = None
    share_class_figi: str | None = None
    cik: str | None = None
    delisted_utc: datetime | None = None
    provider_last_updated_utc: datetime | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        # Massive uses lowercase 'p' in preferred-share symbols. Preserve the
        # provider ticker exactly apart from surrounding whitespace.
        value = value.strip()
        if not value:
            raise ValueError("ticker cannot be blank")
        return value

    @field_validator("composite_figi", "share_class_figi", "cik", "primary_exchange", "security_type")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = str(value).strip().upper()
        return value or None

    @field_validator("delisted_utc", "provider_last_updated_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value is not None else None


class InstrumentRegistryEntry(BaseModel):
    instrument_id: str
    identity_key: str
    identity_quality: InstrumentIdentityQuality
    latest_ticker: str
    latest_name: str | None = None
    composite_figi: str | None = None
    share_class_figi: str | None = None
    cik: str | None = None
    primary_exchange: str | None = None
    security_type: str | None = None
    first_observed_date: date
    last_observed_date: date
    active_latest: bool


class TickerObservationSummary(BaseModel):
    instrument_id: str
    ticker: str
    first_observed_date: date
    last_observed_date: date
    observation_count: int = Field(ge=1)

    @field_validator("ticker")
    @classmethod
    def preserve_observed_ticker_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ticker cannot be blank")
        return value


class ReferenceSnapshotResult(BaseModel):
    as_of_date: date
    row_count: int = Field(ge=0)
    instrument_count: int = Field(ge=0)
    path: str
    skipped: bool = False
    strong_identity_count: int = Field(default=0, ge=0)
    medium_identity_count: int = Field(default=0, ge=0)
    fallback_identity_count: int = Field(default=0, ge=0)


class TickerChangeEvent(BaseModel):
    """One provider-reported ticker label in an instrument's event timeline."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    provider: DataProvider = DataProvider.MASSIVE
    event_type: str = Field(default="ticker_change", min_length=1)
    event_date: date
    ticker: str = Field(min_length=1, max_length=64)
    query_identifier: str = Field(min_length=1)
    query_identifier_type: str = Field(min_length=1)
    continuity_authority: bool
    provider_name: str | None = None
    fetched_at_utc: datetime

    @field_validator("ticker")
    @classmethod
    def preserve_provider_ticker_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ticker cannot be blank")
        return value

    @field_validator("query_identifier")
    @classmethod
    def normalize_query_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query_identifier cannot be blank")
        return value

    @field_validator("fetched_at_utc")
    @classmethod
    def normalize_fetched_at(cls, value: datetime) -> datetime:
        return to_utc(value)


class TickerEventSyncResult(BaseModel):
    instrument_id: str
    query_identifier: str
    query_identifier_type: str
    continuity_authority: bool
    event_count: int = Field(ge=0)
    path: str
    skipped: bool = False


class TickerValidityInterval(BaseModel):
    """Half-open provider-authoritative ticker interval: [from, to)."""

    instrument_id: str
    ticker: str
    valid_from_date: date
    valid_to_date_exclusive: date | None = None
    query_identifier: str
    query_identifier_type: str
    continuity_authority: bool = True
    evidence_source: str = "massive_ticker_events"

    @field_validator("ticker")
    @classmethod
    def preserve_interval_ticker_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ticker cannot be blank")
        return value


class TickerReuseObservation(BaseModel):
    """The same exact provider ticker observed on a different instrument identity."""

    ticker: str
    other_instrument_id: str
    current_first_observed_date: date
    current_last_observed_date: date
    other_first_observed_date: date
    other_last_observed_date: date
    observation_ranges_overlap: bool

    @field_validator("ticker")
    @classmethod
    def preserve_reuse_ticker_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ticker cannot be blank")
        return value


class IdentityContinuityReport(BaseModel):
    """Deterministic reconciliation of snapshot aliases and provider event evidence."""

    instrument_id: str
    snapshot_ticker: str
    as_of_date: date
    status: str
    continuity_confirmed: bool
    blocking_anomaly: bool
    observed_tickers: list[TickerObservationSummary] = Field(default_factory=list)
    authoritative_events: list[TickerChangeEvent] = Field(default_factory=list)
    authoritative_intervals: list[TickerValidityInterval] = Field(default_factory=list)
    unresolved_observed_tickers: list[str] = Field(default_factory=list)
    ticker_reuse_observations: list[TickerReuseObservation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
