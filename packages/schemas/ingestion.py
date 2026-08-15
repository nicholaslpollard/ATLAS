from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.core.enums import DataProvider, DatasetType, IngestionStatus, ValidationStatus
from packages.core.identifiers import stable_id
from packages.core.timestamps import to_utc


class ProviderFileDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: DataProvider
    dataset: DatasetType
    trading_date: date
    remote_key: str = Field(min_length=1)
    expected_size_bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = None

    @property
    def source_id(self) -> str:
        return stable_id(self.provider, self.dataset, self.trading_date, self.remote_key, prefix="src")


class IngestionPlanItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    descriptor: ProviderFileDescriptor
    local_path: Path
    reason: str = Field(min_length=1)
    priority: int = Field(default=100, ge=0)

    @property
    def plan_id(self) -> str:
        return stable_id(self.descriptor.source_id, self.local_path.as_posix(), prefix="plan")


class IngestionManifestRecord(BaseModel):
    source_id: str
    provider: DataProvider
    dataset: DatasetType
    trading_date: date
    remote_key: str
    local_path: Path
    status: IngestionStatus = IngestionStatus.PLANNED
    validation_status: ValidationStatus = ValidationStatus.UNKNOWN
    size_bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = None
    attempt_count: int = Field(default=0, ge=0)
    last_error: str | None = None
    downloaded_at_utc: datetime | None = None
    validated_at_utc: datetime | None = None
    processed_at_utc: datetime | None = None

    @field_validator("downloaded_at_utc", "validated_at_utc", "processed_at_utc")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value is not None else None


class IngestionCheckpoint(BaseModel):
    checkpoint_id: str
    stage: str
    source_id: str | None = None
    cursor: str | None = None
    completed_units: int = Field(default=0, ge=0)
    total_units: int | None = Field(default=None, ge=0)
    updated_at_utc: datetime

    @field_validator("updated_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)


class ReconciliationSummary(BaseModel):
    trading_date: date
    dataset: DatasetType
    streamed_rows: int = Field(ge=0)
    finalized_rows: int = Field(ge=0)
    matching_rows: int = Field(ge=0)
    inserted_rows: int = Field(ge=0)
    corrected_rows: int = Field(ge=0)
    removed_rows: int = Field(ge=0)
    unresolved_rows: int = Field(ge=0)
