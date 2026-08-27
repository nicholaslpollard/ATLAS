from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .phase25_gate6_policy import phase25_gate6_policy_fingerprint
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
)


PHASE25_GATE7_CONTRACT_VERSION = (
    "phase25-gate7-v1-provider-free-exact-pit-market-ticker-route-context"
)
ACCEPTED_GATE6_POLICY_FINGERPRINT = (
    "5ee92c766031fcf02bf8b80d9a1f4366e7bb6faa8c3634236ad438ef11f52da0"
)

PHASE25_GATE7_PROVIDER_READS = 0
PHASE25_GATE7_PROVIDER_WRITES = 0
PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED = False
PHASE25_GATE7_MARKET_RESEARCH_RECONSTRUCTION_ALLOWED = True
PHASE25_GATE7_TICKER_RESEARCH_RECONSTRUCTION_ALLOWED = True
PHASE25_GATE7_EXACT_PIT_IDENTITY_REQUIRED = True
PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY = False
PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED = True
PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED = False
PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED = False
PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED = False


@dataclass(frozen=True, slots=True)
class Phase25Gate7Policy:
    contract_version: str = PHASE25_GATE7_CONTRACT_VERSION
    gate6_policy_fingerprint: str = ACCEPTED_GATE6_POLICY_FINGERPRINT
    provider_reads: int = PHASE25_GATE7_PROVIDER_READS
    provider_writes: int = PHASE25_GATE7_PROVIDER_WRITES
    operational_regime_writes_allowed: bool = PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED
    market_research_reconstruction_allowed: bool = PHASE25_GATE7_MARKET_RESEARCH_RECONSTRUCTION_ALLOWED
    ticker_research_reconstruction_allowed: bool = PHASE25_GATE7_TICKER_RESEARCH_RECONSTRUCTION_ALLOWED
    exact_pit_identity_required: bool = PHASE25_GATE7_EXACT_PIT_IDENTITY_REQUIRED
    sector_mapping_authority: bool = PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY
    strategy_routing_allowed: bool = PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED
    strategy_rule_evaluation_allowed: bool = PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED
    strategy_returns_read_allowed: bool = PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED
    support_replacement_allowed: bool = PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


PHASE25_GATE7_POLICY = Phase25Gate7Policy()


def phase25_gate7_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE7_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


assert phase25_gate6_policy_fingerprint() == ACCEPTED_GATE6_POLICY_FINGERPRINT
assert PHASE25_GATE7_PROVIDER_READS == PHASE25_GATE7_PROVIDER_WRITES == 0
assert PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED is False
assert PHASE25_GATE7_MARKET_RESEARCH_RECONSTRUCTION_ALLOWED is True
assert PHASE25_GATE7_TICKER_RESEARCH_RECONSTRUCTION_ALLOWED is True
assert PHASE25_GATE7_EXACT_PIT_IDENTITY_REQUIRED is True
assert PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY is False
assert PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED is True
assert PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED is False
assert PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED is False
assert PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED is False
assert PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
assert PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
assert PHASE25_PHASE11_SUPPORT_WRITES == 0
assert PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
