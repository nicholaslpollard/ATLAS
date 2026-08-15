from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.core.timestamps import to_utc
from packages.core.validation import validate_ohlc


class CanonicalBar(BaseModel):
    """Canonical ATLAS market bar.

    Canonical bars contain provider/source facts only. Indicators, regimes,
    strategy outputs, predictions, and trading decisions do not belong here.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1, max_length=32)
    timestamp_utc: datetime
    session_date: date
    timeframe: Timeframe
    session_segment: SessionSegment

    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    vwap: float | None = Field(default=None, gt=0)
    transaction_count: int | None = Field(default=None, ge=0)

    provider: DataProvider
    dataset: DatasetType
    source_id: str = Field(min_length=1)
    is_adjusted: bool | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("symbol cannot be blank")
        return value

    @field_validator("timestamp_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def validate_bar(self) -> "CanonicalBar":
        validate_ohlc(self.open, self.high, self.low, self.close)
        if self.timeframe == Timeframe.DAY_1 and self.session_segment not in {
            SessionSegment.REGULAR,
            SessionSegment.FULL_DAY,
        }:
            raise ValueError("1d canonical bars must be regular-session or full-day bars")
        return self


class BarKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp_utc: datetime
    timeframe: Timeframe
    session_segment: SessionSegment

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)
