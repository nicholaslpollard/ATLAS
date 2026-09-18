from __future__ import annotations

import hashlib
import json


RECURRENT_CYCLE_RECEIPT_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-cycle-receipt-v1",
    "scope": "PRODUCT_SIMULATION_DURABLE_ACCEPTED_EVIDENCE_CYCLE_ORCHESTRATION",
    "runtime": "atlas-simulation-recurrent-durable-runtime-v1",
    "cycle_stage_order": [
        "CLOSE",
        "RESERVE",
        "ENTRY",
        "MARK",
        "COMPLETE",
    ],
    "cycle_id_required": True,
    "cycle_fingerprint_required": True,
    "source_checkpoint_sha256_required": True,
    "source_snapshot_fingerprint_required": True,
    "current_checkpoint_sha256_required": True,
    "accepted_evidence_only": True,
    "provider_acquisition_outside_orchestrator": True,
    "broker_acquisition_outside_orchestrator": True,
    "stage_action_fingerprints_required": True,
    "stage_receipt_atomic_fsync_required": True,
    "stage_order_monotonic_required": True,
    "exact_stage_reuse_idempotent": True,
    "conflicting_stage_reuse_fails_closed": True,
    "interrupted_post_runtime_pre_receipt_stage_reapply_supported": True,
    "one_runtime_owner_assumed": True,
    "no_hidden_state_reconstruction": True,
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
        RECURRENT_CYCLE_RECEIPT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT = contract_fingerprint()
