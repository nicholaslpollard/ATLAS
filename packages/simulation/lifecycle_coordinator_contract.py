from __future__ import annotations

import hashlib
import json


SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-coordinator-v1",
    "scope": "PRODUCT_SIMULATION_SINGLE_CYCLE_ATOMIC_LIFECYCLE_OWNER",
    "source": "atlas-simulation-open-position-account-state-v1",
    "initial_closeout_state": "deterministically_initialized_from_exact_source",
    "closeout_account_is_authoritative_current_book_state": True,
    "current_marked_state_is_optional_projection_of_exact_current_book_state": True,
    "new_closeout_mutation_invalidates_prior_marked_state": True,
    "identical_idempotent_exit_reuse_does_not_mutate_or_invalidate": True,
    "mark_publication_requires_complete_fresh_current_position_coverage": True,
    "atomic_snapshot_pair_required": True,
    "thread_safe_single_owner": True,
    "lock_kind": "RLock",
    "deterministic_exit_batch_order": True,
    "deterministic_replay_required": True,
    "no_filesystem_reconstruction": True,
    "no_provider_reads_or_writes": True,
    "no_broker_reads_or_writes": True,
    "no_order_creation": True,
    "single_cycle_only": True,
    "new_reservations_supported": False,
    "new_entries_after_initial_source_supported": False,
    "reentry_supported": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT = contract_fingerprint()
