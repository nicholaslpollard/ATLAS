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
        value = value.strip().upper()
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


class ReferenceSnapshotResult(BaseModel):
    as_of_date: date
    row_count: int = Field(ge=0)
    instrument_count: int = Field(ge=0)
    path: str
    skipped: bool = False
    strong_identity_count: int = Field(default=0, ge=0)
    medium_identity_count: int = Field(default=0, ge=0)
    fallback_identity_count: int = Field(default=0, ge=0)
