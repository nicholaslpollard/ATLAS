from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.execution import BrokerName, ExecutionEnvironment


EXECUTION_CASE_DISPOSITION_CONTRACT_VERSION = (
    "execution-case-disposition-v1-explicit-block-submit-existing-uncertain"
)


class ExecutionCaseDisposition(StrEnum):
    BLOCKED = "BLOCKED"
    SHADOW_EXECUTED = "SHADOW_EXECUTED"
    PAPER_SUBMITTED = "PAPER_SUBMITTED"
    EXISTING_RECONCILED = "EXISTING_RECONCILED"
    PROVIDER_UNCERTAIN = "PROVIDER_UNCERTAIN"


class ExecutionCaseDispositionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = EXECUTION_CASE_DISPOSITION_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    phase13_case_sha256: str = Field(min_length=64, max_length=64)
    environment: ExecutionEnvironment
    broker: BrokerName
    disposition: ExecutionCaseDisposition
    intent_path: str | None = None
    intent_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    attempt_path: str | None = None
    attempt_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    quote_read: bool
    broker_initialized: bool
    provider_submission_attempted: bool
    provider_submission_uncertain: bool
    broker_write_count: int | None = Field(default=0, ge=0)
    order_write_count: int | None = Field(default=0, ge=0)
    live_write_count: int = Field(ge=0)
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_disposition(self) -> "ExecutionCaseDispositionRecord":
        if (self.intent_path is None) != (self.intent_sha256 is None):
            raise ValueError("intent path/hash must be supplied together")
        if (self.attempt_path is None) != (self.attempt_sha256 is None):
            raise ValueError("attempt path/hash must be supplied together")
        if self.disposition == ExecutionCaseDisposition.BLOCKED:
            if self.attempt_path is not None:
                raise ValueError("blocked case cannot carry a completed execution attempt")
            if self.broker_write_count != 0 or self.order_write_count != 0 or self.live_write_count != 0:
                raise ValueError("definitively blocked case must have zero writes")
            if self.provider_submission_uncertain:
                raise ValueError("blocked case cannot remain provider-uncertain")
        elif self.disposition == ExecutionCaseDisposition.PROVIDER_UNCERTAIN:
            if not self.provider_submission_attempted or not self.provider_submission_uncertain:
                raise ValueError("uncertain disposition must follow an uncertain provider submission")
            if self.attempt_path is not None:
                raise ValueError("uncertain submission cannot claim a completed attempt record")
            if self.broker_write_count is not None or self.order_write_count is not None:
                raise ValueError("uncertain provider submission must leave broker/order write count unknown")
            if self.live_write_count:
                raise ValueError("Phase 15 uncertain submission cannot be live")
        else:
            if self.attempt_path is None:
                raise ValueError("completed/reconciled disposition requires an attempt artifact")
            if self.provider_submission_uncertain:
                raise ValueError("completed disposition cannot remain provider-uncertain")
            if self.broker_write_count is None or self.order_write_count is None:
                raise ValueError("completed disposition requires known write counts")
        if self.disposition == ExecutionCaseDisposition.PAPER_SUBMITTED:
            if not self.provider_submission_attempted or self.broker_write_count != 1 or self.order_write_count != 1:
                raise ValueError("paper submission must record one broker/order write")
        if self.disposition in {
            ExecutionCaseDisposition.SHADOW_EXECUTED,
            ExecutionCaseDisposition.EXISTING_RECONCILED,
        }:
            if self.broker_write_count != 0 or self.order_write_count != 0:
                raise ValueError("shadow/idempotent reconciliation cannot claim provider writes")
        if self.live_write_count != 0:
            raise ValueError("Phase 15 live writes are forbidden")
        if not self.reason_codes:
            raise ValueError("execution case disposition requires reason codes")
        return self
