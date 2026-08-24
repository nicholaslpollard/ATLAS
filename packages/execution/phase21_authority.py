from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from packages.schemas.execution import (
    BrokerName,
    BrokerOrderPlan,
    ExecutionEnvironment,
    ExecutionIntent,
)


PHASE21_POLICY_CONTRACT_VERSION = (
    "phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny"
)
PHASE21_AUTHORITY_CONTRACT_VERSION = (
    "phase21-paper-execution-authority-v1-broker-paper-run-scoped"
)
PHASE21_PAPER_PROVIDER_SUBMIT_ENABLED_BY_DEFAULT = False
PHASE21_LIVE_EXECUTION_ENABLED = False
PHASE21_AUTOMATIC_BROKER_FAILOVER = False
PHASE21_OPERATION = "PROVIDER_SUBMIT"
PHASE21_ALLOWED_BROKERS = (BrokerName.WEBULL, BrokerName.ALPACA)


class Phase21AuthorizationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase21_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE21_POLICY_CONTRACT_VERSION,
        "paper_provider_submit_enabled_by_default": PHASE21_PAPER_PROVIDER_SUBMIT_ENABLED_BY_DEFAULT,
        "live_execution_enabled": PHASE21_LIVE_EXECUTION_ENABLED,
        "automatic_broker_failover": PHASE21_AUTOMATIC_BROKER_FAILOVER,
        "operation": PHASE21_OPERATION,
        "allowed_brokers": [item.value for item in PHASE21_ALLOWED_BROKERS],
        "environment": ExecutionEnvironment.PAPER.value,
        "authority_scope": "broker_environment_execution_run",
        "missing_or_mismatched_authority": "FAIL_CLOSED_BEFORE_NEW_PROVIDER_SUBMIT",
        "existing_idempotent_order": "NO_NEW_MUTATION_AUTHORITY_REQUIRED",
        "phase18_certification_authority": "REMAINS_SEPARATE_AND_REQUIRED",
    }


def phase21_policy_fingerprint() -> str:
    return _stable_hash(phase21_policy_payload())


def _normalize_paper_broker(broker: BrokerName | str) -> BrokerName:
    normalized = BrokerName(broker)
    if normalized not in PHASE21_ALLOWED_BROKERS:
        raise Phase21AuthorizationError("Phase 21 paper execution authority requires Webull or Alpaca")
    return normalized


def phase21_confirmation_text(execution_scope_id: str, broker: BrokerName | str) -> str:
    normalized = _normalize_paper_broker(broker)
    scope = str(execution_scope_id).strip()
    if not scope.startswith("p21-") or len(scope) != 36:
        raise Phase21AuthorizationError("Phase 21 execution scope id is malformed")
    return f"AUTHORIZE_ATLAS_PAPER_SUBMIT:{normalized.value}:{scope}"


@dataclass(frozen=True)
class Phase21PaperExecutionChallenge:
    contract_version: str
    policy_fingerprint: str
    execution_scope_id: str
    broker: BrokerName
    environment: ExecutionEnvironment
    operation: str
    required_confirmation: str

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "policy_fingerprint": self.policy_fingerprint,
            "execution_scope_id": self.execution_scope_id,
            "broker": self.broker.value,
            "environment": self.environment.value,
            "operation": self.operation,
            "authority_required": True,
        }


@dataclass(frozen=True)
class Phase21PaperExecutionAuthority:
    contract_version: str
    policy_fingerprint: str
    execution_scope_id: str
    broker: BrokerName
    environment: ExecutionEnvironment
    operation: str
    explicitly_authorized: bool
    confirmation: str

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "policy_fingerprint": self.policy_fingerprint,
            "execution_scope_id": self.execution_scope_id,
            "broker": self.broker.value,
            "environment": self.environment.value,
            "operation": self.operation,
            "explicitly_authorized": self.explicitly_authorized,
            "confirmation_validated": True,
        }


def derive_phase15_paper_execution_scope_id(
    *,
    as_of_date: date,
    phase15_input_fingerprint: str,
    phase15_policy_fingerprint: str,
    broker: BrokerName | str,
) -> str:
    normalized = _normalize_paper_broker(broker)
    input_fp = str(phase15_input_fingerprint).strip()
    policy_fp = str(phase15_policy_fingerprint).strip()
    if len(input_fp) != 64 or len(policy_fp) != 64:
        raise Phase21AuthorizationError("Phase 15 execution scope requires exact 64-character fingerprints")
    payload = {
        "phase21_policy_fingerprint": phase21_policy_fingerprint(),
        "scope_kind": "PHASE15_OPERATIONAL_PAPER_RUN",
        "as_of_date": as_of_date.isoformat(),
        "phase15_input_fingerprint": input_fp,
        "phase15_policy_fingerprint": policy_fp,
        "broker": normalized.value,
        "environment": ExecutionEnvironment.PAPER.value,
    }
    return "p21-" + _stable_hash(payload)[:32]


def derive_phase18_paper_execution_scope_id(intent: ExecutionIntent) -> str:
    if intent.environment != ExecutionEnvironment.PAPER:
        raise Phase21AuthorizationError("Phase 18 compatibility scope requires a PAPER intent")
    normalized = _normalize_paper_broker(intent.broker)
    payload = {
        "phase21_policy_fingerprint": phase21_policy_fingerprint(),
        "scope_kind": "PHASE18_CERTIFICATION_PAPER_SUBMIT",
        "intent_id": intent.intent_id,
        "instrument_id": intent.instrument_id,
        "as_of_date": intent.as_of_date.isoformat(),
        "phase13_case_sha256": intent.phase13_case_sha256,
        "phase14_acceptance_sha256": intent.phase14_acceptance_sha256,
        "broker": normalized.value,
        "environment": intent.environment.value,
    }
    return "p21-" + _stable_hash(payload)[:32]


def derive_phase18_operational_validation_scope_id(
    plan: BrokerOrderPlan,
    *,
    broker: BrokerName | str,
) -> str:
    normalized = _normalize_paper_broker(broker)
    payload = {
        "phase21_policy_fingerprint": phase21_policy_fingerprint(),
        "scope_kind": "PHASE18_OPERATIONAL_VALIDATION_PAPER_SUBMIT",
        "broker": normalized.value,
        "environment": ExecutionEnvironment.PAPER.value,
        "client_order_id": plan.client_order_id,
        "intent_id": plan.intent_id,
        "ticker": plan.ticker,
        "plan_fingerprint": _stable_hash(plan.model_dump(mode="json")),
    }
    return "p21-" + _stable_hash(payload)[:32]


def build_phase15_paper_execution_challenge(
    *,
    as_of_date: date,
    phase15_input_fingerprint: str,
    phase15_policy_fingerprint: str,
    broker: BrokerName | str,
) -> Phase21PaperExecutionChallenge:
    normalized = _normalize_paper_broker(broker)
    scope = derive_phase15_paper_execution_scope_id(
        as_of_date=as_of_date,
        phase15_input_fingerprint=phase15_input_fingerprint,
        phase15_policy_fingerprint=phase15_policy_fingerprint,
        broker=normalized,
    )
    return _challenge(scope, normalized)


def build_phase18_paper_execution_challenge(
    intent: ExecutionIntent,
) -> Phase21PaperExecutionChallenge:
    normalized = _normalize_paper_broker(intent.broker)
    return _challenge(derive_phase18_paper_execution_scope_id(intent), normalized)


def build_phase18_operational_validation_challenge(
    plan: BrokerOrderPlan,
    *,
    broker: BrokerName | str,
) -> Phase21PaperExecutionChallenge:
    normalized = _normalize_paper_broker(broker)
    scope = derive_phase18_operational_validation_scope_id(plan, broker=normalized)
    return _challenge(scope, normalized)


def _challenge(
    execution_scope_id: str,
    broker: BrokerName,
) -> Phase21PaperExecutionChallenge:
    return Phase21PaperExecutionChallenge(
        contract_version=PHASE21_AUTHORITY_CONTRACT_VERSION,
        policy_fingerprint=phase21_policy_fingerprint(),
        execution_scope_id=execution_scope_id,
        broker=broker,
        environment=ExecutionEnvironment.PAPER,
        operation=PHASE21_OPERATION,
        required_confirmation=phase21_confirmation_text(execution_scope_id, broker),
    )


def authorize_phase21_paper_execution(
    challenge: Phase21PaperExecutionChallenge,
    *,
    explicitly_authorized: bool,
    confirmation: str,
) -> Phase21PaperExecutionAuthority:
    return Phase21PaperExecutionAuthority(
        contract_version=challenge.contract_version,
        policy_fingerprint=challenge.policy_fingerprint,
        execution_scope_id=challenge.execution_scope_id,
        broker=challenge.broker,
        environment=challenge.environment,
        operation=challenge.operation,
        explicitly_authorized=bool(explicitly_authorized),
        confirmation=str(confirmation),
    )


def require_phase21_paper_execution_authority(
    authority: Phase21PaperExecutionAuthority | None,
    *,
    expected_execution_scope_id: str | None,
    broker: BrokerName | str,
    environment: ExecutionEnvironment | str,
) -> Phase21PaperExecutionAuthority:
    normalized_broker = _normalize_paper_broker(broker)
    normalized_environment = ExecutionEnvironment(environment)
    if normalized_environment != ExecutionEnvironment.PAPER:
        raise Phase21AuthorizationError("Phase 21 provider-submit authority applies to PAPER only")
    if authority is None:
        raise Phase21AuthorizationError("explicit Phase 21 paper execution authority is required")
    if authority.contract_version != PHASE21_AUTHORITY_CONTRACT_VERSION:
        raise Phase21AuthorizationError("Phase 21 authority contract version mismatch")
    if authority.policy_fingerprint != phase21_policy_fingerprint():
        raise Phase21AuthorizationError("Phase 21 policy fingerprint mismatch")
    if not authority.explicitly_authorized:
        raise Phase21AuthorizationError("Phase 21 paper execution was not explicitly authorized")
    if authority.operation != PHASE21_OPERATION:
        raise Phase21AuthorizationError("Phase 21 authority operation mismatch")
    if authority.broker != normalized_broker:
        raise Phase21AuthorizationError("Phase 21 authority broker mismatch")
    if authority.environment != ExecutionEnvironment.PAPER:
        raise Phase21AuthorizationError("Phase 21 authority environment mismatch")
    scope = "" if expected_execution_scope_id is None else str(expected_execution_scope_id).strip()
    if authority.execution_scope_id != scope:
        raise Phase21AuthorizationError("Phase 21 execution scope mismatch")
    expected_confirmation = phase21_confirmation_text(scope, normalized_broker)
    if authority.confirmation != expected_confirmation:
        raise Phase21AuthorizationError("Phase 21 run-scoped confirmation mismatch")
    return authority
