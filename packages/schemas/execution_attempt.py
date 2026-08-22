from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.execution import (
    BrokerOrderPlan,
    BrokerOrderSnapshot,
    BrokerPreflightResult,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
    ExecutionIntent,
)


EXECUTION_RISK_REVALIDATION_CONTRACT_VERSION = (
    "execution-risk-revalidation-v1-current-broker-phase13-envelope"
)
EXECUTION_ATTEMPT_CONTRACT_VERSION = (
    "execution-attempt-v1-reconciled-preflight-idempotent-paper-shadow"
)


class ExecutionRiskRevalidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = EXECUTION_RISK_REVALIDATION_CONTRACT_VERSION
    checked_at_utc: datetime
    account_equity: float = Field(gt=0.0)
    account_gross_market_value: float = Field(ge=0.0)
    open_positions_before: int = Field(ge=0)
    existing_same_name_market_value: float = Field(ge=0.0)
    proposed_loss_at_stop: float = Field(gt=0.0)
    proposed_notional: float = Field(gt=0.0)
    projected_loss_fraction: float = Field(ge=0.0)
    projected_single_name_fraction: float = Field(ge=0.0)
    projected_gross_fraction: float = Field(ge=0.0)
    projected_position_count: int = Field(ge=1)
    max_abs_correlation: float | None = Field(default=None, ge=0.0, le=1.0)
    admissible: bool
    reason_codes: tuple[str, ...]

    @field_validator("checked_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("execution risk timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_risk(self) -> "ExecutionRiskRevalidation":
        if not self.reason_codes:
            raise ValueError("execution risk revalidation requires reason codes")
        if self.open_positions_before > 0 and self.max_abs_correlation is None:
            raise ValueError("existing broker positions require current correlation evidence")
        return self


class ExecutionAttemptRecord(BaseModel):
    """One auditable Phase 15 entry attempt.

    The record proves what ATLAS was authorized to submit, the current broker exposure
    revalidation, broker preflight, and exact order state. It does not imply a position
    was opened unless the normalized order snapshot says it filled.
    """

    model_config = ConfigDict(frozen=True)

    contract_version: str = EXECUTION_ATTEMPT_CONTRACT_VERSION
    attempted_at_utc: datetime
    intent: ExecutionIntent
    order_plan: BrokerOrderPlan
    reconciliation_before: BrokerReconciliationSnapshot
    risk_revalidation: ExecutionRiskRevalidation
    preflight: BrokerPreflightResult
    order_snapshot: BrokerOrderSnapshot
    existing_order_reused: bool
    provider_submission_performed: bool
    broker_write_count: int
    order_write_count: int
    live_submission_performed: bool = False

    @field_validator("attempted_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("execution attempt timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_attempt(self) -> "ExecutionAttemptRecord":
        if self.order_plan.intent_id != self.intent.intent_id:
            raise ValueError("execution attempt order plan differs from intent")
        if self.order_snapshot.client_order_id != self.order_plan.client_order_id:
            raise ValueError("execution attempt order snapshot differs from order plan")
        if self.preflight.intent_id != self.intent.intent_id:
            raise ValueError("execution attempt preflight differs from intent")
        if self.reconciliation_before.broker != self.intent.broker:
            raise ValueError("execution attempt reconciliation broker differs from intent")
        if self.reconciliation_before.environment != self.intent.environment:
            raise ValueError("execution attempt reconciliation environment differs from intent")
        if self.preflight.broker != self.intent.broker or self.order_snapshot.broker != self.intent.broker:
            raise ValueError("execution attempt broker evidence differs from intent")
        if not self.reconciliation_before.reconciled:
            raise ValueError("execution attempt requires a reconciled broker snapshot")
        if self.reconciliation_before.account.trading_blocked:
            raise ValueError("execution attempt cannot submit through a blocked account")
        if not self.risk_revalidation.admissible:
            raise ValueError("execution attempt requires current broker risk admission")
        if not self.preflight.accepted:
            raise ValueError("execution attempt requires accepted broker preflight")
        if self.existing_order_reused and self.provider_submission_performed:
            raise ValueError("idempotent existing-order reuse cannot perform a new submission")
        if self.provider_submission_performed:
            if self.intent.environment != ExecutionEnvironment.PAPER:
                raise ValueError("Phase 15 provider submission is permitted only in paper environment")
            if self.broker_write_count != 1 or self.order_write_count != 1:
                raise ValueError("one provider submission must report exactly one broker/order write")
        else:
            if self.broker_write_count != 0 or self.order_write_count != 0:
                raise ValueError("non-submission attempt cannot report broker/order writes")
        if self.live_submission_performed:
            raise ValueError("Phase 15 live submission is forbidden")
        return self
