from __future__ import annotations

import hashlib
import json


RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-lifecycle-checkpoint-v1",
    "scope": "PRODUCT_SIMULATION_DURABLE_RECURRENT_COORDINATOR_SNAPSHOT",
    "payload": "atlas-simulation-recurrent-lifecycle-coordinator-v1",
    "atomic_sibling_temp_replace_required": True,
    "fsync_required": True,
    "self_hash_required": True,
    "snapshot_fingerprint_required": True,
    "account_state_fingerprint_required": True,
    "account_ledger_fingerprint_required": True,
    "marked_state_fingerprint_when_present_required": True,
    "previous_checkpoint_history_preserved": True,
    "history_content_addressed_by_checkpoint_sha256": True,
    "monotonic_revision_required": True,
    "same_revision_requires_identical_snapshot": True,
    "account_ledger_prefix_preservation_required": True,
    "missing_current_with_existing_history_fails_closed": True,
    "restore_revalidates_full_dataclass_contracts": True,
    "research_artifact_reconstruction_forbidden": True,
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
        RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
