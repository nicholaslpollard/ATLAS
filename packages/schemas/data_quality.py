from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, computed_field

from packages.core.enums import DataQualityCode, DataQualitySeverity, DatasetType, ValidationStatus
from packages.core.timestamps import to_utc


class DataQualityIssue(BaseModel):
    code: DataQualityCode
    severity: DataQualitySeverity
    message: str = Field(min_length=1)
    symbol: str | None = None
    timestamp_utc: datetime | None = None
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("timestamp_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value is not None else None


class DataQualityReport(BaseModel):
    dataset: DatasetType
    trading_date: date | None = None
    checked_rows: int = Field(default=0, ge=0)
    score: float = Field(default=100.0, ge=0, le=100)
    issues: list[DataQualityIssue] = Field(default_factory=list)

    @computed_field
    @property
    def status(self) -> ValidationStatus:
        if any(issue.severity == DataQualitySeverity.CRITICAL for issue in self.issues):
            return ValidationStatus.INVALID
        if any(issue.severity == DataQualitySeverity.ERROR for issue in self.issues):
            return ValidationStatus.INVALID
        if self.issues:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID

    @computed_field
    @property
    def blocking_issue_count(self) -> int:
        return sum(
            issue.severity in {DataQualitySeverity.ERROR, DataQualitySeverity.CRITICAL}
            for issue in self.issues
        )
