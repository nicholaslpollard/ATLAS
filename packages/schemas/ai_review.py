from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AI_REVIEW_PAYLOAD_CONTRACT_VERSION = "ai-review-payload-v1-grounded-three-disposition-audit"
AI_REVIEW_RECORD_CONTRACT_VERSION = "ai-review-record-v1-phase13-hash-bound-provider-audited"
ALERT_RECORD_CONTRACT_VERSION = "alert-record-v1-engine-vs-ai-artifact-only"


class AIReviewDisposition(StrEnum):
    APPROVE = "APPROVE"
    CAUTIOUS = "CAUTIOUS"
    REJECT = "REJECT"


class GroundedStatement(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=500)
    evidence_paths: tuple[str, ...] = Field(min_length=1, max_length=8)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("grounded statement cannot be blank")
        return cleaned

    @field_validator("evidence_paths")
    @classmethod
    def clean_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in values if item.strip())
        if not cleaned:
            raise ValueError("grounded statement requires evidence paths")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("grounded statement evidence paths must be unique")
        return cleaned


class AIReviewPayload(BaseModel):
    """Model-produced audit content only; contains no mutable trade plan fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = AI_REVIEW_PAYLOAD_CONTRACT_VERSION
    disposition: AIReviewDisposition
    summary: str = Field(min_length=1, max_length=1000)
    reasons: tuple[GroundedStatement, ...] = Field(min_length=1, max_length=6)
    risk_flags: tuple[GroundedStatement, ...] = Field(default=(), max_length=8)
    disagreements: tuple[GroundedStatement, ...] = Field(default=(), max_length=8)

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("AI review summary cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_semantics(self) -> "AIReviewPayload":
        all_statements = (*self.reasons, *self.risk_flags, *self.disagreements)
        texts = [item.text for item in all_statements]
        if len(texts) != len(set(texts)):
            raise ValueError("AI review statements must be unique")
        if self.disposition == AIReviewDisposition.APPROVE and self.disagreements:
            raise ValueError("APPROVE cannot carry deterministic disagreements; use CAUTIOUS or REJECT")
        return self


class AIReviewRecord(BaseModel):
    """Persisted, hash-bound audit record surrounding one model payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = AI_REVIEW_RECORD_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    phase13_case_sha256: str = Field(min_length=64, max_length=64)
    phase13_case_contract_version: str = Field(min_length=1)
    prompt_contract_version: str = Field(min_length=1)
    prompt_fingerprint: str = Field(min_length=64, max_length=64)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    response_id: str | None = None
    raw_response_path: str | None = None
    raw_response_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    reviewed_at_utc: datetime
    review: AIReviewPayload
    disposition_is_trade_signal: bool = False
    ai_changed_deterministic_case: bool = False
    ai_created_order: bool = False

    @model_validator(mode="after")
    def validate_authority(self) -> "AIReviewRecord":
        if (self.raw_response_path is None) != (self.raw_response_sha256 is None):
            raise ValueError("raw response path/hash must be supplied together")
        if self.disposition_is_trade_signal:
            raise ValueError("AI disposition cannot be a trade signal")
        if self.ai_changed_deterministic_case:
            raise ValueError("AI cannot change the deterministic Phase 13 case")
        if self.ai_created_order:
            raise ValueError("AI cannot create an order")
        return self


class AlertArtifactRecord(BaseModel):
    """Validated Engine-vs-AI alert artifact; this is not a delivery or order object."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = ALERT_RECORD_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    phase13_case_sha256: str = Field(min_length=64, max_length=64)
    ai_review_sha256: str = Field(min_length=64, max_length=64)
    disposition: AIReviewDisposition
    engine_summary: str = Field(min_length=1, max_length=2000)
    ai_summary: str = Field(min_length=1, max_length=1000)
    risk_flags: tuple[str, ...] = Field(default=(), max_length=8)
    disagreements: tuple[str, ...] = Field(default=(), max_length=8)
    external_delivery_enabled: bool = False
    delivered: bool = False
    execution_present: bool = False

    @model_validator(mode="after")
    def validate_alert(self) -> "AlertArtifactRecord":
        if self.external_delivery_enabled or self.delivered:
            raise ValueError("Phase 14 alert records are artifact-only and cannot be delivered")
        if self.execution_present:
            raise ValueError("Phase 14 alert artifact cannot contain execution state")
        return self
