from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.core.enums import (
    DataProvider,
    LiveConnectionState,
    LiveFeedMode,
    LiveFreshness,
    SessionSegment,
)
from packages.core.timestamps import to_utc
from packages.core.validation import validate_ohlc


class LiveMinuteAggregate(BaseModel):
    """Provisional provider minute bar used by ATLAS live state.

    Live bars are never canonical facts. They remain provisional until a finalized
    provider file is ingested through the historical/canonical pipeline.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1, max_length=32)
    bar_start_utc: datetime
    bar_end_utc: datetime
    session_date: date
    session_segment: SessionSegment
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    vwap: float | None = Field(default=None, gt=0)
    accumulated_volume: float | None = Field(default=None, ge=0)
    official_open: float | None = Field(default=None, gt=0)
    daily_vwap: float | None = Field(default=None, gt=0)
    average_trade_size: float | None = Field(default=None, ge=0)
    otc: bool = False
    provider: DataProvider = DataProvider.MASSIVE
    feed_mode: LiveFeedMode
    expected_delay_seconds: int = Field(ge=0)
    received_at_utc: datetime

    @field_validator("symbol")
    @classmethod
    def preserve_symbol_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("symbol cannot be blank")
        return value

    @field_validator("bar_start_utc", "bar_end_utc", "received_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def validate_bar(self) -> "LiveMinuteAggregate":
        validate_ohlc(self.open, self.high, self.low, self.close)
        if self.bar_end_utc <= self.bar_start_utc:
            raise ValueError("bar_end_utc must be after bar_start_utc")
        return self


class LiveQuote(BaseModel):
    """Latest provisional NBBO observation for one exact provider-native symbol."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1, max_length=32)
    provider_timestamp_utc: datetime
    session_date: date
    session_segment: SessionSegment
    bid_price: float = Field(ge=0)
    bid_size: int = Field(ge=0)
    bid_exchange: int | None = Field(default=None, ge=0)
    ask_price: float = Field(ge=0)
    ask_size: int = Field(ge=0)
    ask_exchange: int | None = Field(default=None, ge=0)
    condition: int | None = None
    indicators: tuple[int, ...] = ()
    sequence: int = Field(ge=0)
    tape: int | None = Field(default=None, ge=0)
    provider: DataProvider = DataProvider.MASSIVE
    feed_mode: LiveFeedMode
    expected_delay_seconds: int = Field(ge=0)
    received_at_utc: datetime

    @field_validator("symbol")
    @classmethod
    def preserve_symbol_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("symbol cannot be blank")
        return value

    @field_validator("provider_timestamp_utc", "received_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)


class LiveSymbolState(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    as_of_utc: datetime
    minute: LiveMinuteAggregate | None = None
    minute_freshness: LiveFreshness = LiveFreshness.UNKNOWN
    quote: LiveQuote | None = None
    quote_freshness: LiveFreshness = LiveFreshness.UNKNOWN

    @field_validator("symbol")
    @classmethod
    def preserve_symbol_case(cls, value: str) -> str:
        return value.strip()

    @field_validator("as_of_utc")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return to_utc(value)


class LiveSessionStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    as_of_utc: datetime
    local_date: date
    is_exchange_session: bool
    session_segment: SessionSegment
    regular_open_utc: datetime | None = None
    regular_close_utc: datetime | None = None
    next_session_date: date | None = None
    next_regular_open_utc: datetime | None = None

    @field_validator("as_of_utc", "regular_open_utc", "regular_close_utc", "next_regular_open_utc")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value is not None else None


class LiveStateSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at_utc: datetime
    feed_mode: LiveFeedMode
    expected_delay_seconds: int = Field(ge=0)
    connection_state: LiveConnectionState
    subscriptions: tuple[str, ...] = ()
    session: LiveSessionStatus
    received_events: int = Field(default=0, ge=0)
    accepted_events: int = Field(default=0, ge=0)
    ignored_out_of_order_events: int = Field(default=0, ge=0)
    parse_errors: int = Field(default=0, ge=0)
    reconnects: int = Field(default=0, ge=0)
    restored_symbol_count: int = Field(default=0, ge=0)
    observed_symbol_count: int = Field(default=0, ge=0)
    last_received_at_utc: datetime | None = None
    symbols: tuple[LiveSymbolState, ...] = ()

    @field_validator("generated_at_utc", "last_received_at_utc")
    @classmethod
    def normalize_snapshot_timestamp(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value is not None else None

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)


class LiveReconciliationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_date: date
    live_bar_count: int = Field(ge=0)
    canonical_bar_count: int = Field(ge=0)
    matched_key_count: int = Field(ge=0)
    live_only_key_count: int = Field(ge=0)
    canonical_only_key_count: int = Field(ge=0)
    value_mismatch_count: int = Field(ge=0)
    exact_match_count: int = Field(ge=0)
    report_path: str | None = None
