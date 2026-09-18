from __future__ import annotations

import hashlib
import json

from packages.simulation.recurrent_cycle_contract import (
    RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT,
)


RECURRENT_CYCLE_RUNNER_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-cycle-runner-v1",
    "scope": "PRODUCT_SIMULATION_DETERMINISTIC_STAGE_ADMISSION_AND_RESTART_RUNNER",
    "cycle_orchestrator_contract_fingerprint": (
        RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT
    ),
    "schedule_id_required": True,
    "scheduled_slot_timezone_aware_required": True,
    "cycle_id_deterministic_from_schedule_and_slot": True,
    "stage_admission_before_runtime_mutation_required": True,
    "stage_admission_source_checkpoint_binding_required": True,
    "stage_admission_source_snapshot_binding_required": True,
    "stage_evidence_source_id_required": True,
    "stage_evidence_source_sha256_required": True,
    "stage_evidence_fingerprint_required": True,
    "stage_admission_atomic_fsync_required": True,
    "stage_admission_self_hash_required": True,
    "exact_admission_reuse_idempotent": True,
    "conflicting_admission_reuse_fails_closed": True,
    "restart_stage_replay_delegated_to_cycle_orchestrator": True,
    "provider_acquisition_outside_runner": True,
    "broker_acquisition_outside_runner": True,
    "scheduler_trigger_authority": False,
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
        RECURRENT_CYCLE_RUNNER_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT = contract_fingerprint()
