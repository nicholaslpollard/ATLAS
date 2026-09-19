from __future__ import annotations

import hashlib
import json


RECURRENT_EXIT_PLAN_REFRESH_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-exit-plan-refresh-v1",
    "scope": "PRODUCT_SIMULATION_POST_ENTRY_DURABLE_EXIT_PLAN_BOOK_REFRESH",
    "cycle_receipt_required": True,
    "cycle_must_be_open": True,
    "required_stage_prefix": ["CLOSE", "RESERVE", "ENTRY"],
    "mark_stage_must_not_be_recorded": True,
    "runtime_must_match_cycle_receipt": True,
    "stable_entry_stage_record_fingerprint_required": True,
    "entry_stage_admission_sha_required": True,
    "current_reserve_bundle_must_match_cycle_when_supplied": True,
    "existing_plan_book_reused_when_valid": True,
    "new_positions_require_current_reserve_decision_evidence": True,
    "explicit_exit_policy_coverage_required_for_new_positions": True,
    "plan_book_atomic_fsync_required": True,
    "refresh_receipt_atomic_fsync_required": True,
    "refresh_receipt_self_fingerprint_required": True,
    "exact_reuse_idempotent": True,
    "conflicting_reuse_fails_closed": True,
    "interrupted_post_book_pre_receipt_recovery_supported": True,
    "effective_time_is_entry_stage_recorded_time": True,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_EXIT_PLAN_REFRESH_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT = contract_fingerprint()
