from __future__ import annotations

import hashlib
import json


PERSISTENT_RECURRENT_RUNTIME_CONTRACT = {
    "contract_id": "atlas-simulation-persistent-recurrent-runtime-v1",
    "scope": "PRODUCT_SIMULATION_PERSISTED_RECURRENT_COORDINATOR_RUNTIME",
    "account_contract": "atlas-simulation-recurrent-lifecycle-account-v1",
    "coordinator_contract": "atlas-simulation-recurrent-lifecycle-coordinator-v1",
    "store_contract": "atlas-simulation-recurrent-runtime-store-v1",
    "restore_only_from_accepted_store": True,
    "explicit_initial_account_required_for_first_bootstrap": True,
    "no_implicit_starting_equity": True,
    "no_artifact_reconstruction_fallback": True,
    "mutation_persisted_before_success_return": True,
    "persistence_failure_rolls_back_in_memory_account": True,
    "persistence_failure_invalidates_transient_marks": True,
    "idempotent_zero_event_mutation_does_not_rewrite_store": True,
    "mark_publication_is_transient_not_persisted": True,
    "restart_requires_fresh_marks": True,
    "single_runtime_lock": True,
    "provider_read_authority": False,
    "provider_write_authority": False,
    "broker_read_authority": False,
    "broker_write_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        PERSISTENT_RECURRENT_RUNTIME_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


PERSISTENT_RECURRENT_RUNTIME_CONTRACT_FINGERPRINT = contract_fingerprint()
