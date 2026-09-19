from __future__ import annotations

import hashlib
import json


RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT = {
    "contract_id": "atlas-recurrent-workstation-acceptance-v1",
    "scope": (
        "PRODUCT_SIMULATION_ISOLATED_WEBULL_SANDBOX_MARKET_HOURS_RESTART_RESUME_ACCEPTANCE"
    ),
    "isolated_live_root_required": True,
    "normal_live_root_forbidden": True,
    "webull_sandbox_l1_read_only": True,
    "operator_supplied_initial_equity_required": True,
    "operator_supplied_entry_fee_required": True,
    "operator_supplied_exit_fee_required": True,
    "reference_fixture_not_strategy_evidence": True,
    "reference_horizon_regular_session_minutes": 1,
    "reference_stop_threshold_fraction": 0.20,
    "reference_target_threshold_fraction": 0.20,
    "process_boundary_after_entry_required": True,
    "process_boundary_before_exact_close_retry_required": True,
    "post_entry_refresh_before_mark_required": True,
    "durable_clock_book_required": True,
    "time_expired_disposition_required": True,
    "price_no_trigger_required_for_time_acceptance": True,
    "time_aware_production_close_required": True,
    "exact_close_retry_no_double_apply_required": True,
    "dashboard_same_authoritative_state_proof_required": True,
    "cycle_health_proof_required": True,
    "final_receipt_self_fingerprint_required": True,
    "provider_reads_allowed_only_for_explicit_quote_capture": True,
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
        RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
