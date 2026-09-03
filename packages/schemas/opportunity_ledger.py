from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.strategy_lab import (
    StrategyAuthority,
    StrategyExecutionMode,
    execution_mode_permitted,
)


OPPORTUNITY_LEDGER_CONTRACT_VERSION = "b33-opportunity-ledger-v1-append-only-shared-replay-product"


class OpportunityEventType(StrEnum):
    ELIGIBLE_SETUP = "ELIGIBLE_SETUP"
    FIRED = "FIRED"
    ROUTED_OUT = "ROUTED_OUT"
    AUTHORITY_BLOCKED = "AUTHORITY_BLOCKED"
    RISK_REJECTED = "RISK_REJECTED"
    NOT_SELECTED = "NOT_SELECTED"
    SHADOW_COUNTERFACTUAL = "SHADOW_COUNTERFACTUAL"
    PLANNED = "PLANNED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXITED = "EXITED"
    UNRECONCILED = "UNRECONCILED"


class OpportunityEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = OPPORTUNITY_LEDGER_CONTRACT_VERSION
    opportunity_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    occurred_at: datetime
    signal_session: date
    instrument_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    strategy_authority: StrategyAuthority
    execution_mode: StrategyExecutionMode
    event_type: OpportunityEventType
    reason_codes: tuple[str, ...] = ()
    is_counterfactual: bool = False
    market_regime: str | None = None
    sector_regime: str | None = None
    ticker_regime: str | None = None
    volatility_bucket: str | None = None
    liquidity_bucket: str | None = None
    data_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    strategy_code_version: str = Field(min_length=1)
    selector_version: str | None = None
    cost_model_version: str = Field(min_length=1)
    risk_model_version: str = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_authority_and_counterfactuals(self) -> "OpportunityEvent":
        if not execution_mode_permitted(self.strategy_authority, self.execution_mode):
            raise ValueError(
                f"{self.execution_mode} is not permitted for authority {self.strategy_authority}"
            )
        if self.event_type == OpportunityEventType.SHADOW_COUNTERFACTUAL and not self.is_counterfactual:
            raise ValueError("SHADOW_COUNTERFACTUAL events must set is_counterfactual=True")
        if self.is_counterfactual and self.event_type in {
            OpportunityEventType.SUBMITTED,
            OpportunityEventType.PARTIALLY_FILLED,
            OpportunityEventType.FILLED,
        }:
            raise ValueError("counterfactual opportunities cannot contain broker execution events")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must be unique")
        return self
