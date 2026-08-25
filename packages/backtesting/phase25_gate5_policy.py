from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_GATE3_ACTIVE,
    PHASE25_GATE3_ENDPOINT,
    PHASE25_GATE3_INCLUDE_INACTIVE,
    PHASE25_GATE3_MARKET,
    PHASE25_GATE3_ORDER,
    PHASE25_GATE3_PAGE_LIMIT,
    PHASE25_GATE3_SORT,
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


PHASE25_GATE5_CONTRACT_VERSION = (
    "phase25-gate5-v1-explicit-cli-resumable-frozen-active-only-bulk-acquisition"
)

# Accepted Phase25 target-evidence fingerprints are immutable. Gate5 lives in a
# separate policy module so later read-only acquisition rules cannot retroactively
# change the evidence contracts that produced Gates0-4.
ACCEPTED_GATE0_POLICY_FINGERPRINT = "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604"
ACCEPTED_GATE1_POLICY_FINGERPRINT = "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207"
ACCEPTED_GATE2_POLICY_FINGERPRINT = "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083"
ACCEPTED_GATE3_POLICY_FINGERPRINT = "d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6"
ACCEPTED_GATE4_POLICY_FINGERPRINT = "e8ef1b2f0d020e579e4c8fc92dfa256fea307ce96ed89cee02c4a812b8398d16"

PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED = True
PHASE25_GATE5_PROVIDER_WRITES_ALLOWED = False
PHASE25_GATE5_AUTHORIZATION_MODE = "EXPLICIT_CLI_SUBCOMMAND"
PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED = False
PHASE25_GATE5_BULK_ACQUISITION_ALLOWED = True
PHASE25_GATE5_GATE4_ACCEPTANCE_REQUIRED = True
PHASE25_GATE5_GATE3_FROZEN_SCOPE_REQUIRED = True
PHASE25_GATE5_PROBE_REFETCH_ALLOWED = False
PHASE25_GATE5_FORCE_REPLACE_ALLOWED = False
PHASE25_GATE5_SKIP_ONLY_VALIDATED_PAIRS = True
PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED = True
PHASE25_GATE5_PROVIDER_NATIVE_TICKER_CASE_PRESERVED = True
PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE = True
PHASE25_GATE5_RESUMABLE_SAME_COMMAND = True


@dataclass(frozen=True, slots=True)
class Phase25Gate5Policy:
    contract_version: str = PHASE25_GATE5_CONTRACT_VERSION
    gate4_policy_fingerprint: str = ACCEPTED_GATE4_POLICY_FINGERPRINT
    authorization_mode: str = PHASE25_GATE5_AUTHORIZATION_MODE
    provider_read_authority_allowed: bool = PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED
    provider_writes_allowed: bool = PHASE25_GATE5_PROVIDER_WRITES_ALLOWED
    interactive_confirmation_required: bool = PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED
    bulk_acquisition_allowed: bool = PHASE25_GATE5_BULK_ACQUISITION_ALLOWED
    gate4_acceptance_required: bool = PHASE25_GATE5_GATE4_ACCEPTANCE_REQUIRED
    gate3_frozen_scope_required: bool = PHASE25_GATE5_GATE3_FROZEN_SCOPE_REQUIRED
    probe_refetch_allowed: bool = PHASE25_GATE5_PROBE_REFETCH_ALLOWED
    force_replace_allowed: bool = PHASE25_GATE5_FORCE_REPLACE_ALLOWED
    skip_only_validated_pairs: bool = PHASE25_GATE5_SKIP_ONLY_VALIDATED_PAIRS
    partial_pair_fails_closed: bool = PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED
    provider_native_ticker_case_preserved: bool = PHASE25_GATE5_PROVIDER_NATIVE_TICKER_CASE_PRESERVED
    defer_registry_rebuild_until_complete: bool = PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE
    resumable_same_command: bool = PHASE25_GATE5_RESUMABLE_SAME_COMMAND
    endpoint: str = PHASE25_GATE3_ENDPOINT
    market: str = PHASE25_GATE3_MARKET
    active: bool = PHASE25_GATE3_ACTIVE
    order: str = PHASE25_GATE3_ORDER
    sort: str = PHASE25_GATE3_SORT
    page_limit: int = PHASE25_GATE3_PAGE_LIMIT
    include_inactive: bool = PHASE25_GATE3_INCLUDE_INACTIVE
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


PHASE25_GATE5_POLICY = Phase25Gate5Policy()


def phase25_gate5_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE5_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


assert phase25_gate0_policy_fingerprint() == ACCEPTED_GATE0_POLICY_FINGERPRINT
assert phase25_gate1_policy_fingerprint() == ACCEPTED_GATE1_POLICY_FINGERPRINT
assert phase25_gate2_policy_fingerprint() == ACCEPTED_GATE2_POLICY_FINGERPRINT
assert phase25_gate3_policy_fingerprint() == ACCEPTED_GATE3_POLICY_FINGERPRINT
assert phase25_gate4_policy_fingerprint() == ACCEPTED_GATE4_POLICY_FINGERPRINT
assert PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED is True
assert PHASE25_GATE5_PROVIDER_WRITES_ALLOWED is False
assert PHASE25_GATE5_AUTHORIZATION_MODE == "EXPLICIT_CLI_SUBCOMMAND"
assert PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED is False
assert PHASE25_GATE5_BULK_ACQUISITION_ALLOWED is True
assert PHASE25_GATE5_GATE4_ACCEPTANCE_REQUIRED is True
assert PHASE25_GATE5_GATE3_FROZEN_SCOPE_REQUIRED is True
assert PHASE25_GATE5_PROBE_REFETCH_ALLOWED is False
assert PHASE25_GATE5_FORCE_REPLACE_ALLOWED is False
assert PHASE25_GATE5_SKIP_ONLY_VALIDATED_PAIRS is True
assert PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED is True
assert PHASE25_GATE5_PROVIDER_NATIVE_TICKER_CASE_PRESERVED is True
assert PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE is True
assert PHASE25_GATE5_RESUMABLE_SAME_COMMAND is True
assert PHASE25_GATE3_ACTIVE is True
assert PHASE25_GATE3_INCLUDE_INACTIVE is False
assert PHASE25_GATE3_PAGE_LIMIT == 1000
assert PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
assert PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
assert PHASE25_PHASE11_SUPPORT_WRITES == 0
assert PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
