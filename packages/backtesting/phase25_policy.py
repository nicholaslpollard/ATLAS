from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date

from packages.regimes.split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    TICKER_HISTORY_ORIGIN_DATE,
)


PHASE25_GATE0_CONTRACT_VERSION = (
    "phase25-gate0-v1-provider-free-production-path-feasibility-inventory"
)
PHASE25_GATE1_CONTRACT_VERSION = (
    "phase25-gate1-v1-provider-free-pit-reference-scope-proof"
)
PHASE25_GATE2_CONTRACT_VERSION = (
    "phase25-gate2-v1-provider-free-active-only-reference-discovery-equivalence"
)
PHASE25_ROUTE_REPLAY_ORIGIN = TICKER_HISTORY_ORIGIN_DATE
PHASE25_MARKET_DAILY_ORIGIN = MARKET_SECTOR_HISTORY_ORIGIN_DATE

PHASE25_PROVIDER_READS = 0
PHASE25_PROVIDER_WRITES = 0
PHASE25_BROKER_READS = 0
PHASE25_BROKER_WRITES = 0
PHASE25_ORDER_WRITES = 0
PHASE25_PAPER_SUBMITS = 0
PHASE25_LIVE_WRITES = 0
PHASE25_PHASE11_SUPPORT_WRITES = 0
PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS = 0
PHASE25_STRATEGY_RULE_CHANGES_ALLOWED = False
PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED = False
PHASE25_SECTOR_FABRICATION_ALLOWED = False
PHASE25_PRE_ORIGIN_INTRADAY_FABRICATION_ALLOWED = False

# Gate1 does not permit carrying later provider metadata backward as if it were a
# point-in-time fact. It may measure such future-only observations, but they remain
# non-authoritative research evidence until an explicit later gate accepts a source.
PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED = False
PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED = False
PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY = True

# Gate2 may prove that inactive reference rows are unnecessary for the discovery
# population, but it has no authority to perform provider reads or to change routing.
PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED = False
PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED = False
PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE = True


@dataclass(frozen=True, slots=True)
class Phase25Gate0Policy:
    contract_version: str = PHASE25_GATE0_CONTRACT_VERSION
    replay_origin: date = PHASE25_ROUTE_REPLAY_ORIGIN
    market_daily_origin: date = PHASE25_MARKET_DAILY_ORIGIN
    provider_reads: int = PHASE25_PROVIDER_READS
    provider_writes: int = PHASE25_PROVIDER_WRITES
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS
    strategy_rule_changes_allowed: bool = PHASE25_STRATEGY_RULE_CHANGES_ALLOWED
    outcome_definition_changes_allowed: bool = PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED
    sector_fabrication_allowed: bool = PHASE25_SECTOR_FABRICATION_ALLOWED
    pre_origin_intraday_fabrication_allowed: bool = PHASE25_PRE_ORIGIN_INTRADAY_FABRICATION_ALLOWED

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["replay_origin"] = self.replay_origin.isoformat()
        payload["market_daily_origin"] = self.market_daily_origin.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class Phase25Gate1Policy:
    contract_version: str = PHASE25_GATE1_CONTRACT_VERSION
    gate0_policy_fingerprint: str = ""
    replay_origin: date = PHASE25_ROUTE_REPLAY_ORIGIN
    provider_reads: int = PHASE25_PROVIDER_READS
    provider_writes: int = PHASE25_PROVIDER_WRITES
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS
    future_reference_metadata_authority_allowed: bool = (
        PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED
    )
    proxy_universe_support_authority_allowed: bool = (
        PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED
    )
    exact_pit_reference_required_for_authoritative_phase7_replay: bool = (
        PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY
    )

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["replay_origin"] = self.replay_origin.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class Phase25Gate2Policy:
    contract_version: str = PHASE25_GATE2_CONTRACT_VERSION
    gate1_policy_fingerprint: str = ""
    replay_origin: date = PHASE25_ROUTE_REPLAY_ORIGIN
    provider_reads: int = PHASE25_PROVIDER_READS
    provider_writes: int = PHASE25_PROVIDER_WRITES
    broker_reads: int = PHASE25_BROKER_READS
    broker_writes: int = PHASE25_BROKER_WRITES
    order_writes: int = PHASE25_ORDER_WRITES
    paper_submits: int = PHASE25_PAPER_SUBMITS
    live_writes: int = PHASE25_LIVE_WRITES
    phase11_support_writes: int = PHASE25_PHASE11_SUPPORT_WRITES
    protected_strategy_evidence_reads: int = PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS
    provider_acquisition_authority_allowed: bool = (
        PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED
    )
    discovery_overrides_allowed: bool = PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED
    requires_materialized_universe_equivalence: bool = (
        PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE
    )

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["replay_origin"] = self.replay_origin.isoformat()
        return payload


PHASE25_GATE0_POLICY = Phase25Gate0Policy()


def phase25_gate0_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE0_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


PHASE25_GATE1_POLICY = Phase25Gate1Policy(
    gate0_policy_fingerprint=phase25_gate0_policy_fingerprint()
)


def phase25_gate1_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE1_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


PHASE25_GATE2_POLICY = Phase25Gate2Policy(
    gate1_policy_fingerprint=phase25_gate1_policy_fingerprint()
)


def phase25_gate2_policy_fingerprint() -> str:
    raw = json.dumps(
        PHASE25_GATE2_POLICY.public_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


assert PHASE25_ROUTE_REPLAY_ORIGIN == date(2021, 8, 16)
assert PHASE25_MARKET_DAILY_ORIGIN == date(2016, 1, 4)
assert PHASE25_PROVIDER_READS == 0
assert PHASE25_PROVIDER_WRITES == 0
assert PHASE25_BROKER_READS == 0
assert PHASE25_BROKER_WRITES == 0
assert PHASE25_ORDER_WRITES == 0
assert PHASE25_PAPER_SUBMITS == 0
assert PHASE25_LIVE_WRITES == 0
assert PHASE25_PHASE11_SUPPORT_WRITES == 0
assert PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
assert PHASE25_STRATEGY_RULE_CHANGES_ALLOWED is False
assert PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED is False
assert PHASE25_SECTOR_FABRICATION_ALLOWED is False
assert PHASE25_PRE_ORIGIN_INTRADAY_FABRICATION_ALLOWED is False
assert PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED is False
assert PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED is False
assert PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY is True
assert PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False
assert PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED is False
assert PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE is True
