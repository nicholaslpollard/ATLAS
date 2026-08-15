from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from packages.core.enums import DatasetType, MaterializationStatus, Timeframe, ValidationStatus
from packages.core.timestamps import to_utc


class MaterializationRecord(BaseModel):
    source_id: str
    dataset: DatasetType
    trading_date: date
    source_path: Path
    source_sha256: str | None = None
    dependency_fingerprint: str | None = None
    status: MaterializationStatus = MaterializationStatus.PLANNED
    staging_path: Path | None = None
    canonical_path: Path | None = None
    derived_paths: dict[str, Path] = Field(default_factory=dict)
    quality_report_path: Path | None = None
    quarantine_path: Path | None = None
    quarantined_symbols: list[str] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.UNKNOWN
    source_rows: int = Field(default=0, ge=0)
    canonical_rows: int = Field(default=0, ge=0)
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    last_error: str | None = None

    @field_validator("started_at_utc", "completed_at_utc")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value else None


class DerivedBarSummary(BaseModel):
    timeframe: Timeframe
    trading_date: date
    path: Path
    row_count: int = Field(ge=0)
