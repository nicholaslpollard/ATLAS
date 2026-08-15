from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from packages.core.enums import DatasetType
from packages.core.timestamps import to_utc


class HistoryLayerAudit(BaseModel):
    name: str
    expected_sessions: int = Field(ge=0)
    present_sessions: int = Field(ge=0)
    missing_sessions: list[date] = Field(default_factory=list)
    bytes_on_disk: int = Field(default=0, ge=0)

    @property
    def complete(self) -> bool:
        return not self.missing_sessions


class ProviderDatasetAudit(HistoryLayerAudit):
    dataset: DatasetType
    invalid_sessions: list[date] = Field(default_factory=list)


class HistoricalLakeAuditReport(BaseModel):
    start_date: date
    end_date: date
    generated_at_utc: datetime
    exchange_sessions: list[date]
    provider: dict[str, ProviderDatasetAudit]
    canonical: dict[str, HistoryLayerAudit]
    derived: dict[str, HistoryLayerAudit]
    quarantine_sessions: list[date] = Field(default_factory=list)
    quarantined_symbols: list[str] = Field(default_factory=list)
    total_bytes_on_disk: int = Field(default=0, ge=0)

    @field_validator("generated_at_utc")
    @classmethod
    def normalize_generated(cls, value: datetime) -> datetime:
        return to_utc(value)


class LegacyImportResult(BaseModel):
    dataset: DatasetType
    discovered_files: int = Field(ge=0)
    imported_files: int = Field(ge=0)
    skipped_files: int = Field(ge=0)
    invalid_files: int = Field(ge=0)
    imported_dates: list[date] = Field(default_factory=list)
    invalid_paths: list[Path] = Field(default_factory=list)


class HistoricalBuildResult(BaseModel):
    start_date: date
    end_date: date
    effective_start_date: date | None = None
    effective_end_date: date | None = None
    sessions_requested: int = Field(ge=0)
    sessions_processed: int = Field(default=0, ge=0)
    inaccessible_sessions_skipped: int = Field(default=0, ge=0)
    daily_downloads_planned: int = Field(default=0, ge=0)
    minute_downloads_planned: int = Field(default=0, ge=0)
    materialized_sessions: int = Field(default=0, ge=0)
    skipped_materializations: int = Field(default=0, ge=0)
    failures: dict[str, str] = Field(default_factory=dict)
    elapsed_seconds: float = Field(default=0.0, ge=0)
