from __future__ import annotations

import hashlib
import json


RECURRENT_RUNTIME_STORE_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-runtime-store-v1",
    "scope": "PRODUCT_SIMULATION_DURABLE_RECURRENT_ACCOUNT_SNAPSHOT_ONLY",
    "stored_account_contract": "atlas-simulation-recurrent-lifecycle-account-v1",
    "single_current_snapshot": True,
    "snapshot_contains_complete_recurrent_ledger": True,
    "snapshot_contains_canonical_closed_history": True,
    "atomic_same_volume_replace_required": True,
    "fsync_before_replace_required": True,
    "exclusive_writer_lock_required": True,
    "compare_and_swap_prior_state_fingerprint_required": True,
    "exact_state_and_ledger_fingerprints_required": True,
    "snapshot_sha256_required": True,
    "post_write_reread_validation_required": True,
    "ledger_event_count_must_not_regress": True,
    "account_time_must_not_regress": True,
    "missing_snapshot_is_explicit_uninitialized_state": True,
    "corrupt_snapshot_fails_closed": True,
    "marked_state_is_transient_not_persisted": True,
    "no_artifact_reconstruction_fallback": True,
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
        RECURRENT_RUNTIME_STORE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_RUNTIME_STORE_CONTRACT_FINGERPRINT = contract_fingerprint()
