from __future__ import annotations

import hashlib
import json


PHASE24_POLICY_CONTRACT_VERSION = (
    "phase24-policy-v1-strategy-evidence-challenger-gate0-local-readonly"
)
PHASE24_ACCEPTED_PHASE23_MERGE = "2004338624766c42b5f4db2bb0976b2047a5c6b0"
PHASE24_GATE0_AS_OF = "2026-08-21"
PHASE24_EXTERNAL_PROVIDER_READS = False
PHASE24_EXTERNAL_PROVIDER_WRITES = False
PHASE24_BROKER_READS = False
PHASE24_BROKER_WRITES = False
PHASE24_ORDER_WRITES = False
PHASE24_PAPER_SUBMITS = False
PHASE24_LIVE_WRITES = False
PHASE24_AUTOMATIC_BROKER_FAILOVER = False
PHASE24_BROWSER_EXECUTION = False
PHASE24_SCHEDULER_EXECUTION = False
PHASE24_POSTGRES_RUNTIME_PROMOTION = False
PHASE24_PRODUCTION_ML_WRITES = False
PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY = False
PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY = False
PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION = False


def phase24_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE24_POLICY_CONTRACT_VERSION,
        "accepted_phase23_merge": PHASE24_ACCEPTED_PHASE23_MERGE,
        "gate0_as_of": PHASE24_GATE0_AS_OF,
        "external_provider_reads": PHASE24_EXTERNAL_PROVIDER_READS,
        "external_provider_writes": PHASE24_EXTERNAL_PROVIDER_WRITES,
        "broker_reads": PHASE24_BROKER_READS,
        "broker_writes": PHASE24_BROKER_WRITES,
        "order_writes": PHASE24_ORDER_WRITES,
        "paper_submits": PHASE24_PAPER_SUBMITS,
        "live_writes": PHASE24_LIVE_WRITES,
        "automatic_broker_failover": PHASE24_AUTOMATIC_BROKER_FAILOVER,
        "browser_execution": PHASE24_BROWSER_EXECUTION,
        "scheduler_execution": PHASE24_SCHEDULER_EXECUTION,
        "postgres_runtime_promotion": PHASE24_POSTGRES_RUNTIME_PROMOTION,
        "production_ml_writes": PHASE24_PRODUCTION_ML_WRITES,
        "phase11_support_replacement_authority": PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY,
        "counterfactual_current_rules_are_authority": PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY,
        "gate0_expose_protected_confirmation": PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION,
    }


def phase24_policy_fingerprint() -> str:
    raw = json.dumps(phase24_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
