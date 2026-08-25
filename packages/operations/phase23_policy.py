from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from packages.schemas.execution import BrokerName


PHASE23_POLICY_CONTRACT_VERSION = (
    "phase23-policy-v1-current-finalized-analysis-explicit-read-authority-no-execution"
)
PHASE23_DEFAULT_BROKER = BrokerName.WEBULL
PHASE23_ALLOWED_BROKERS = (BrokerName.WEBULL, BrokerName.ALPACA)
PHASE23_LIVE_EXECUTION_ENABLED = False
PHASE23_AUTOMATIC_BROKER_FAILOVER = False
PHASE23_BROWSER_EXECUTION_ENABLED = False
PHASE23_SCHEDULER_EXECUTION_ENABLED = False
PHASE23_POSTGRES_RUNTIME_REQUIRED = False
PHASE23_BROKER_MUTATIONS_ALLOWED = False
PHASE23_ORDER_WRITES_ALLOWED = False
PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED = False
PHASE23_ARBITRARY_CASE_INPUT_ALLOWED = False

MASSIVE_MARKET_REFERENCE_READS = "MASSIVE_MARKET_REFERENCE_READS"
MASSIVE_RESEARCH_READS = "MASSIVE_RESEARCH_READS"
PAPER_BROKER_READS = "PAPER_BROKER_READS"
AI_REVIEW_CALLS = "AI_REVIEW_CALLS"
PHASE23_EXTERNAL_READ_CLASSES = (
    MASSIVE_MARKET_REFERENCE_READS,
    MASSIVE_RESEARCH_READS,
    PAPER_BROKER_READS,
    AI_REVIEW_CALLS,
)

# Accepted Phase 11 support is frozen until a separate strategy-evaluation phase
# explicitly replaces it. Routine operation may not reinterpret MIXED as SUPPORTED.
PHASE23_FROZEN_STRATEGY_SUPPORT = {
    "breakdown_short_v1": "UNSUPPORTED",
    "breakout_long_v1": "UNSUPPORTED",
    "momentum_long_v1": "MIXED",
    "momentum_short_v1": "UNSUPPORTED",
    "pullback_long_v1": "MIXED",
    "pullback_short_v1": "UNSUPPORTED",
    "trend_following_long_v1": "MIXED",
    "trend_following_short_v1": "UNSUPPORTED",
}
PHASE23_FROZEN_SUPPORTED_STRATEGIES: tuple[str, ...] = ()
PHASE23_ACCEPTED_ML_MODEL_ID = "mlmodel-hgb15-2026-08-14-d485e6c287bacce1"


class Phase23AuthorizationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase23_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE23_POLICY_CONTRACT_VERSION,
        "default_broker": PHASE23_DEFAULT_BROKER.value,
        "allowed_brokers": [item.value for item in PHASE23_ALLOWED_BROKERS],
        "finalized_session_required": True,
        "prepare_provider_free": True,
        "external_read_classes": list(PHASE23_EXTERNAL_READ_CLASSES),
        "live_execution_enabled": PHASE23_LIVE_EXECUTION_ENABLED,
        "automatic_broker_failover": PHASE23_AUTOMATIC_BROKER_FAILOVER,
        "browser_execution_enabled": PHASE23_BROWSER_EXECUTION_ENABLED,
        "scheduler_execution_enabled": PHASE23_SCHEDULER_EXECUTION_ENABLED,
        "postgres_runtime_required": PHASE23_POSTGRES_RUNTIME_REQUIRED,
        "broker_mutations_allowed": PHASE23_BROKER_MUTATIONS_ALLOWED,
        "order_writes_allowed": PHASE23_ORDER_WRITES_ALLOWED,
        "paper_submit_authority_allowed": PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED,
        "arbitrary_case_input_allowed": PHASE23_ARBITRARY_CASE_INPUT_ALLOWED,
        "phase20_provider_free_policy_unchanged": True,
        "phase22_execution_separate": True,
        "historical_strategy_study_rerun_in_routine_cycle": False,
        "frozen_strategy_support": dict(sorted(PHASE23_FROZEN_STRATEGY_SUPPORT.items())),
        "frozen_supported_strategy_ids": list(PHASE23_FROZEN_SUPPORTED_STRATEGIES),
        "accepted_ml_model_id": PHASE23_ACCEPTED_ML_MODEL_ID,
        "zero_promotion_is_valid": True,
    }


def phase23_policy_fingerprint() -> str:
    return _stable_hash(phase23_policy_payload())


@dataclass(frozen=True, slots=True)
class Phase23ReadChallenge:
    as_of_date: date
    broker: BrokerName
    execution_scope_id: str
    external_read_classes: tuple[str, ...]
    required_confirmation: str

    def public_dict(self) -> dict[str, object]:
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "broker": self.broker.value,
            "execution_scope_id": self.execution_scope_id,
            "external_read_classes": list(self.external_read_classes),
        }


@dataclass(frozen=True, slots=True)
class Phase23ReadAuthority:
    as_of_date: date
    broker: BrokerName
    execution_scope_id: str
    external_read_classes: tuple[str, ...]
    explicitly_authorized: bool

    def public_dict(self) -> dict[str, object]:
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "broker": self.broker.value,
            "execution_scope_id": self.execution_scope_id,
            "external_read_classes": list(self.external_read_classes),
            "explicitly_authorized": self.explicitly_authorized,
        }


def build_phase23_read_challenge(
    *,
    as_of_date: date,
    broker: BrokerName | str,
    run_scope_payload: dict[str, object],
    external_read_classes: tuple[str, ...],
) -> Phase23ReadChallenge:
    selected = BrokerName(broker)
    if selected not in PHASE23_ALLOWED_BROKERS:
        raise Phase23AuthorizationError("Phase 23 supports only Webull or Alpaca PAPER read context")
    unknown = sorted(set(external_read_classes).difference(PHASE23_EXTERNAL_READ_CLASSES))
    if unknown:
        raise Phase23AuthorizationError("unknown Phase 23 external-read class: " + ", ".join(unknown))
    normalized = tuple(sorted(set(external_read_classes)))
    scope_payload = {
        "policy_fingerprint": phase23_policy_fingerprint(),
        "as_of_date": as_of_date.isoformat(),
        "broker": selected.value,
        "external_read_classes": list(normalized),
        "run_scope_payload": run_scope_payload,
    }
    scope_id = "p23-" + _stable_hash(scope_payload)[:40]
    required = f"AUTHORIZE_ATLAS_PHASE23_READS:{selected.value}:{scope_id}"
    return Phase23ReadChallenge(
        as_of_date=as_of_date,
        broker=selected,
        execution_scope_id=scope_id,
        external_read_classes=normalized,
        required_confirmation=required,
    )


def authorize_phase23_reads(
    challenge: Phase23ReadChallenge,
    *,
    confirmation: str,
    explicitly_authorized: bool,
) -> Phase23ReadAuthority:
    if not explicitly_authorized or confirmation != challenge.required_confirmation:
        raise Phase23AuthorizationError("exact Phase 23 run-scoped read confirmation was not satisfied")
    return Phase23ReadAuthority(
        as_of_date=challenge.as_of_date,
        broker=challenge.broker,
        execution_scope_id=challenge.execution_scope_id,
        external_read_classes=challenge.external_read_classes,
        explicitly_authorized=True,
    )


def require_phase23_read_authority(
    authority: Phase23ReadAuthority | None,
    *,
    challenge: Phase23ReadChallenge,
) -> Phase23ReadAuthority:
    if authority is None or not authority.explicitly_authorized:
        raise Phase23AuthorizationError("Phase 23 external reads are default-deny")
    if authority.as_of_date != challenge.as_of_date:
        raise Phase23AuthorizationError("Phase 23 read authority date mismatch")
    if authority.broker != challenge.broker:
        raise Phase23AuthorizationError("Phase 23 read authority broker mismatch")
    if authority.execution_scope_id != challenge.execution_scope_id:
        raise Phase23AuthorizationError("Phase 23 read authority scope mismatch")
    if authority.external_read_classes != challenge.external_read_classes:
        raise Phase23AuthorizationError("Phase 23 read authority class mismatch")
    return authority
