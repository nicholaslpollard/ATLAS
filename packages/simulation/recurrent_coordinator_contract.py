from __future__ import annotations

import hashlib
import json


RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-lifecycle-coordinator-v1",
    "scope": "PRODUCT_SIMULATION_ATOMIC_REPEATED_CYCLE_OWNER",
    "account_input_output": "atlas-simulation-recurrent-lifecycle-account-v1",
    "reservation_transition": "atlas-simulation-recurrent-reservation-transitions-v1",
    "entry_fill_evidence": "atlas-simulation-recurrent-entry-fill-evidence-v1",
    "funding_terms": "atlas-simulation-recurrent-funding-terms-v1",
    "position_transition": "atlas-simulation-recurrent-position-transition-v1",
    "marked_projection": "atlas-simulation-recurrent-marked-account-v1",
    "exit_fill_evidence": "atlas-simulation-recurrent-exit-fill-evidence-v1",
    "close_transition": "atlas-simulation-recurrent-close-position-transition-v1",
    "single_atomic_account_owner": True,
    "thread_safe_rlock": True,
    "same_recurrent_account_contract_across_cycles": True,
    "account_mutation_invalidates_prior_valuation": True,
    "idempotent_reuse_preserves_current_valuation": True,
    "unique_mark_publication_advances_revision": True,
    "ledger_event_count_advances_revision": True,
    "zero_money_ledger_events_advance_revision": True,
    "dashboard_pair_is_atomic_account_plus_matching_mark": True,
    "no_filesystem_reconstruction": True,
    "no_provider_reads_or_writes": True,
    "no_broker_reads_or_writes": True,
    "no_order_creation": True,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT = contract_fingerprint()
