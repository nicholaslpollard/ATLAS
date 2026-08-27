from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .phase25_gate5_policy import (
    ACCEPTED_GATE0_POLICY_FINGERPRINT,
    ACCEPTED_GATE1_POLICY_FINGERPRINT,
    ACCEPTED_GATE2_POLICY_FINGERPRINT,
    ACCEPTED_GATE3_POLICY_FINGERPRINT,
    ACCEPTED_GATE4_POLICY_FINGERPRINT,
    phase25_gate5_policy_fingerprint,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


PHASE25_GATE6_CONTRACT_VERSION = (
    "phase25-gate6-v1-provider-free-phase7-discovery-chronological-reconstruction"
)
ACCEPTED_GATE5_POLICY_FINGERPRINT = (
    "0e2060d91838c506d8b7c720fd38c06186dac8e4b4587385079b49cae519b8a0"
)

PHASE25_GATE6_PROVIDER_READS = 0
PHASE25_GATE6_PROVIDER_WRITES = 0
PHASE25_GATE6_MATERIALIZE_MISSING_PHASE7_ALLOWED = True
PHASE25_GATE6_MATERIALIZE_MISSING_DISCOVERY_FOUNDATION_ALLOWED = True
PHASE25_GATE6_MATERIALIZE_MISSING_DISCOVERY_SCORE_ALLOWED = True
PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED = False
PHASE25_GATE6_DISCOVERY_STATE_RESEARCH_NAMESPACE_ONLY = True
PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED = False
PHASE25_GATE6_EXACT_PIT_REFERENCE_REQUIRED = True
PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED = False
PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED = False
PHASE25_GATE6_REGIME_ROUTING_ALLOWED = False
PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED = False
PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED = False


@dataclass(frozen=True, slots=True)
class Phase25Gate6Policy:
    contract_version: str = PHASE25_GATE6_CONTRACT_VERSION
    gate5_policy_fingerprint: str = ACCEPTED_GATE5_POLICY_FINGERPRINT
    provider_reads: int = PHASE25_GATE6_PROVIDER_READS
    provider_writes: int = PHASE25_GATE6_PROVIDER_WRITES
    materialize_missing_phase7_allowed: bool = PHASE25_GATE6_MATERIALIZE_MISSING_PHASE7_ALLOWED
    materialize_missing_discovery_foundation_allowed: bool = PHASE25_GATE6_MATERIALIZE_MISSING_DISCOVERY_FOUNDATION_ALLOWED
    materialize_missing_discovery_score_allowed: bool = PHASE25_GATE6_MATERIALIZE_MISSING_DISCOVERY_SCORE_ALLOWED
    overwrite_existing_artifacts_allowed: bool = PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED
    discovery_state_research_namespace_only: bool = PHASE25_GATE6_DISCOVERY_STATE_RESEARCH_NAMESPACE_ONLY
    operational_discovery_state_writes_allowed: bool = PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED
    exact_pit_reference_required: bool = PHASE25_GATE6_EXACT_PIT_REFERENCE_REQUIRED
    discovery_overrides_allowed: bool = PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED
    strategy_returns_read_allowed: bool = PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED
    regime_routing_allowed: bool = PHASE25_GATE6_REGIME_ROUTING_ALLOWED
    strategy_rule_evaluation_allowed: bool = PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED
    support_replacement_allowed: bool = PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


PHASE25_GATE6_POLICY = Phase25Gate6Policy()


def phase25_gate6_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE6_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


assert phase25_gate0_policy_fingerprint() == ACCEPTED_GATE0_POLICY_FINGERPRINT
assert phase25_gate1_policy_fingerprint() == ACCEPTED_GATE1_POLICY_FINGERPRINT
assert phase25_gate2_policy_fingerprint() == ACCEPTED_GATE2_POLICY_FINGERPRINT
assert phase25_gate3_policy_fingerprint() == ACCEPTED_GATE3_POLICY_FINGERPRINT
assert phase25_gate4_policy_fingerprint() == ACCEPTED_GATE4_POLICY_FINGERPRINT
assert phase25_gate5_policy_fingerprint() == ACCEPTED_GATE5_POLICY_FINGERPRINT
assert PHASE25_GATE6_PROVIDER_READS == PHASE25_GATE6_PROVIDER_WRITES == 0
assert PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED is False
assert PHASE25_GATE6_DISCOVERY_STATE_RESEARCH_NAMESPACE_ONLY is True
assert PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED is False
assert PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED is False
assert PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED is False
assert PHASE25_GATE6_REGIME_ROUTING_ALLOWED is False
assert PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED is False
assert PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED is False
assert PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
assert PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
assert PHASE25_PHASE11_SUPPORT_WRITES == 0
assert PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
