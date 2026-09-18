from __future__ import annotations

import hashlib
import json


RECURRENT_CYCLE_HEALTH_CONTRACT = {
    "contract_id": "atlas-control-plane-recurrent-cycle-health-v1",
    "scope": "READ_ONLY_DURABLE_RECURRENT_CYCLE_AND_ADMISSION_HEALTH",
    "checkpoint_contract": "atlas-simulation-recurrent-lifecycle-checkpoint-v1",
    "cycle_contract": "atlas-simulation-recurrent-cycle-receipt-v1",
    "runner_contract": "atlas-simulation-recurrent-cycle-runner-v1",
    "validate_checkpoint_history": True,
    "validate_all_cycle_receipts": True,
    "validate_cycle_receipt_filename_binding": True,
    "validate_all_stage_admissions": True,
    "reject_orphan_stage_admissions": True,
    "validate_recorded_stage_admission_lineage": True,
    "allow_legacy_recorded_stage_without_admission_as_degraded": True,
    "allow_next_stage_admission_without_stage_record": True,
    "reject_future_stage_admission": True,
    "latest_cycle_deterministic_by_created_at_then_id": True,
    "checkpoint_divergence_requires_pending_admission_recovery_or_invalid": True,
    "read_only": True,
    "provider_read_authority": False,
    "provider_write_authority": False,
    "broker_read_authority": False,
    "broker_write_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_CYCLE_HEALTH_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT = contract_fingerprint()
