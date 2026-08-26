from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from packages.backtesting.outcomes import DEFAULT_COST_GRID_BPS, STRATEGY_OUTCOME_CONTRACT_VERSION
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START

from .phase25_gate7_policy import phase25_gate7_policy_fingerprint
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_ROUTE_REPLAY_ORIGIN,
)


PHASE25_GATE8_CONTRACT_VERSION = (
    "phase25-gate8-v1-development-only-production-path-incumbent-attribution"
)
ACCEPTED_GATE7_POLICY_FINGERPRINT = (
    "2800bd82670b8f763a9c5f5c080301e20ab6462f82dd949f7cec0a800e989c31"
)

PHASE25_GATE8_DEVELOPMENT_START = PHASE25_ROUTE_REPLAY_ORIGIN
PHASE25_GATE8_PROTECTED_START = date.fromisoformat(ML_WALK_FORWARD_FINAL_HOLDOUT_START)
PHASE25_GATE8_DEVELOPMENT_END = PHASE25_GATE8_PROTECTED_START - timedelta(days=1)
PHASE25_GATE8_COST_GRID_BPS = DEFAULT_COST_GRID_BPS
PHASE25_GATE8_OUTCOME_CONTRACT_VERSION = STRATEGY_OUTCOME_CONTRACT_VERSION

PHASE25_GATE8_PROVIDER_READS = 0
PHASE25_GATE8_PROVIDER_WRITES = 0
PHASE25_GATE8_STRATEGY_RULE_EVALUATION_ALLOWED = True
PHASE25_GATE8_STRATEGY_RETURNS_READ_ALLOWED = True
PHASE25_GATE8_BROAD_COMPARATOR_ALLOWED = True
PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED = False
PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED = False
PHASE25_GATE8_STRATEGY_RULE_CHANGES_ALLOWED = False
PHASE25_GATE8_OUTCOME_CHANGES_ALLOWED = False


@dataclass(frozen=True, slots=True)
class Phase25Gate8Policy:
    contract_version: str = PHASE25_GATE8_CONTRACT_VERSION
    gate7_policy_fingerprint: str = ACCEPTED_GATE7_POLICY_FINGERPRINT
    development_start: str = PHASE25_GATE8_DEVELOPMENT_START.isoformat()
    development_end: str = PHASE25_GATE8_DEVELOPMENT_END.isoformat()
    protected_start: str = PHASE25_GATE8_PROTECTED_START.isoformat()
    cost_grid_bps: tuple[float, ...] = PHASE25_GATE8_COST_GRID_BPS
    outcome_contract_version: str = PHASE25_GATE8_OUTCOME_CONTRACT_VERSION
    provider_reads: int = PHASE25_GATE8_PROVIDER_READS
    provider_writes: int = PHASE25_GATE8_PROVIDER_WRITES
    strategy_rule_evaluation_allowed: bool = PHASE25_GATE8_STRATEGY_RULE_EVALUATION_ALLOWED
    strategy_returns_read_allowed: bool = PHASE25_GATE8_STRATEGY_RETURNS_READ_ALLOWED
    broad_comparator_allowed: bool = PHASE25_GATE8_BROAD_COMPARATOR_ALLOWED
    protected_evidence_allowed: bool = PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED
    support_replacement_allowed: bool = PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED
    strategy_rule_changes_allowed: bool = PHASE25_GATE8_STRATEGY_RULE_CHANGES_ALLOWED
    outcome_changes_allowed: bool = PHASE25_GATE8_OUTCOME_CHANGES_ALLOWED
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["cost_grid_bps"] = list(self.cost_grid_bps)
        return payload


PHASE25_GATE8_POLICY = Phase25Gate8Policy()


def phase25_gate8_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE8_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


assert phase25_gate7_policy_fingerprint() == ACCEPTED_GATE7_POLICY_FINGERPRINT
assert PHASE25_GATE8_DEVELOPMENT_START == date(2021, 8, 16)
assert PHASE25_GATE8_DEVELOPMENT_END < PHASE25_GATE8_PROTECTED_START
assert PHASE25_GATE8_COST_GRID_BPS == (0.0, 5.0, 10.0, 25.0)
assert PHASE25_GATE8_OUTCOME_CONTRACT_VERSION == "strategy-outcome-v1-direction-adjusted-three-session-return"
assert PHASE25_GATE8_PROVIDER_READS == PHASE25_GATE8_PROVIDER_WRITES == 0
assert PHASE25_GATE8_STRATEGY_RULE_EVALUATION_ALLOWED is True
assert PHASE25_GATE8_STRATEGY_RETURNS_READ_ALLOWED is True
assert PHASE25_GATE8_BROAD_COMPARATOR_ALLOWED is True
assert PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED is False
assert PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED is False
assert PHASE25_GATE8_STRATEGY_RULE_CHANGES_ALLOWED is False
assert PHASE25_GATE8_OUTCOME_CHANGES_ALLOWED is False
assert PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
assert PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
assert PHASE25_PHASE11_SUPPORT_WRITES == 0
assert PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
