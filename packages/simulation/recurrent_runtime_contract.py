from __future__ import annotations

import hashlib
import json


RECURRENT_DURABLE_RUNTIME_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-durable-runtime-v1",
    "scope": "PRODUCT_SIMULATION_DURABLE_RECURRENT_MUTATION_TRANSACTION_BOUNDARY",
    "engine": "atlas-simulation-recurrent-lifecycle-coordinator-v1",
    "checkpoint": "atlas-simulation-recurrent-lifecycle-checkpoint-v1",
    "one_runtime_lock_required": True,
    "pre_mutation_snapshot_required": True,
    "expected_previous_checkpoint_sha_required": True,
    "successful_state_change_requires_verified_checkpoint": True,
    "idempotent_no_state_change_skips_checkpoint_growth": True,
    "checkpoint_failure_requires_durable_readback": True,
    "durable_before_snapshot_means_in_memory_rollback": True,
    "durable_after_snapshot_means_commit_accepted": True,
    "unclassifiable_durable_state_means_uncertain_lockout": True,
    "uncertain_runtime_blocks_reads_and_mutations": True,
    "explicit_checkpoint_reload_can_clear_uncertain_state": True,
    "coordinator_remains_filesystem_io_free": True,
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
        RECURRENT_DURABLE_RUNTIME_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_DURABLE_RUNTIME_CONTRACT_FINGERPRINT = contract_fingerprint()
