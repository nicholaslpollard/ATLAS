from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from packages.schemas.execution import BrokerName, BrokerReconciliationSnapshot, ExecutionEnvironment


BROKER_SWITCH_AUTHORIZATION_CONTRACT_VERSION = (
    "broker-switch-authorization-v1-explicit-flat-reconciled-both-sides"
)


class BrokerSwitchAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = BROKER_SWITCH_AUTHORIZATION_CONTRACT_VERSION
    generated_at_utc: datetime
    environment: ExecutionEnvironment
    current_broker: BrokerName
    target_broker: BrokerName
    current_reconciliation: BrokerReconciliationSnapshot
    target_reconciliation: BrokerReconciliationSnapshot
    explicit_user_or_control_plane_request: bool
    authorized: bool
    reason_codes: tuple[str, ...]

    @field_validator("generated_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("broker-switch timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_authorization(self) -> "BrokerSwitchAuthorization":
        if self.current_broker == self.target_broker:
            raise ValueError("broker switch requires two different brokers")
        if self.environment == ExecutionEnvironment.LIVE:
            raise ValueError("Phase 15 live broker switching is not promoted")
        if self.current_reconciliation.broker != self.current_broker:
            raise ValueError("current reconciliation does not match current broker")
        if self.target_reconciliation.broker != self.target_broker:
            raise ValueError("target reconciliation does not match target broker")
        if self.current_reconciliation.environment != self.environment:
            raise ValueError("current reconciliation environment differs from switch environment")
        if self.target_reconciliation.environment != self.environment:
            raise ValueError("target reconciliation environment differs from switch environment")
        expected = (
            self.explicit_user_or_control_plane_request
            and self.current_reconciliation.safe_to_switch_broker
            and self.target_reconciliation.safe_to_switch_broker
        )
        if self.authorized != expected:
            raise ValueError("broker-switch authorization does not match explicit flat/reconciled rule")
        if not self.reason_codes:
            raise ValueError("broker-switch authorization requires reason codes")
        return self
