from __future__ import annotations

from dataclasses import dataclass
from datetime import date


ALPACA_BACKFILL_CONTRACT_VERSION = "historical-backfill-v1-alpaca-raw-sip-2016-2021"
ALPACA_BACKFILL_START = date(2016, 1, 4)
ALPACA_BACKFILL_END = date(2021, 8, 15)
ALPACA_MASSIVE_SEAM_START = date(2021, 8, 16)
ALPACA_BACKFILL_FEED = "sip"
ALPACA_BACKFILL_ADJUSTMENT = "raw"
ALPACA_BACKFILL_ASOF = "-"
ALPACA_BACKFILL_TIMEFRAME = "1Day"
ALPACA_BACKFILL_PAGE_LIMIT = 10_000
ALPACA_BACKFILL_SYMBOL_BATCH_SIZE = 100
ALPACA_BACKFILL_REQUESTS_PER_MINUTE = 180
ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED = False
ALPACA_BACKFILL_ACCEPTED_PHASE10_MODEL_RETRAINED = False


@dataclass(frozen=True, slots=True)
class BackfillGate:
    number: int
    name: str
    purpose: str


ALPACA_BACKFILL_GATES = (
    BackfillGate(1, "acquisition_storage_contract", "Lock source semantics, immutable payload storage, hashing, pagination, and restart rules."),
    BackfillGate(2, "historical_symbol_inventory", "Build a multi-source candidate inventory and prove observation-driven discovery on a pilot."),
    BackfillGate(3, "raw_historical_acquisition", "Acquire the complete 2016-01-04 through 2021-08-15 raw SIP daily-bar candidate surface with checkpoints."),
    BackfillGate(4, "corporate_action_identity_segmentation", "Persist corporate-action evidence and split ticker-reuse/name-change histories into identity intervals."),
    BackfillGate(5, "provider_completeness_quality", "Audit duplicates, missing sessions, geometry, volume, extreme returns, symbol coverage, and acquisition completeness."),
    BackfillGate(6, "candidate_canonical_materialization", "Normalize validated Alpaca history into an isolated candidate canonical namespace without touching production canonical history."),
    BackfillGate(7, "massive_seam_reconciliation", "Reconcile the candidate history against Massive over a protected overlap window across prices, volume, features, and identities."),
    BackfillGate(8, "canonical_history_promotion", "Promote only accepted pre-2021 candidate partitions into the production canonical daily lake with provenance and rollback records."),
    BackfillGate(9, "feature_replay_2016", "Replay the 33 accepted daily features from the new 2016 origin and verify deterministic continuity across the seam."),
    BackfillGate(10, "regime_replay_extension", "Version and replay market/sector regime history using the added warm-up period; compare overlap before promotion."),
    BackfillGate(11, "longer_history_ml_evaluation", "Build a separately versioned longer-history ML dataset and evaluate it walk-forward; never overwrite the accepted Phase 10 model by assumption."),
    BackfillGate(12, "final_reproducibility_acceptance", "Verify hashes, manifests, identity boundaries, canonical provenance, feature/regime replay, and any promoted ML artifacts."),
)


def gate(number: int) -> BackfillGate:
    for item in ALPACA_BACKFILL_GATES:
        if item.number == number:
            return item
    raise KeyError(f"unknown Alpaca backfill gate: {number}")


def validate_backfill_contract() -> None:
    assert len(ALPACA_BACKFILL_GATES) == 12
    assert tuple(item.number for item in ALPACA_BACKFILL_GATES) == tuple(range(1, 13))
    assert ALPACA_BACKFILL_END < ALPACA_MASSIVE_SEAM_START
    assert (ALPACA_BACKFILL_FEED, ALPACA_BACKFILL_ADJUSTMENT, ALPACA_BACKFILL_ASOF) == ("sip", "raw", "-")
    assert ALPACA_BACKFILL_TIMEFRAME == "1Day"
    assert ALPACA_BACKFILL_PAGE_LIMIT == 10_000
    assert ALPACA_BACKFILL_SYMBOL_BATCH_SIZE == 100
    assert ALPACA_BACKFILL_REQUESTS_PER_MINUTE == 180
    assert not ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED
    assert not ALPACA_BACKFILL_ACCEPTED_PHASE10_MODEL_RETRAINED
