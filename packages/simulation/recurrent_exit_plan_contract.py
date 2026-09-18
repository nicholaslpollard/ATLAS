from __future__ import annotations

import hashlib
import json


RECURRENT_STOCK_EXIT_PLAN_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-stock-exit-plan-v1",
    "scope": "PRODUCT_SIMULATION_PHASE13_GEOMETRY_TO_ACTUAL_FILL_EXIT_PLAN",
    "phase13_case_required": True,
    "phase13_policy_fingerprint_required": True,
    "phase13_review_ready_required": True,
    "available_geometry_required": True,
    "stock_long_only_v1": True,
    "exact_position_case_identity_required": True,
    "case_not_after_position_open_required": True,
    "reference_absolute_prices_non_executable": True,
    "risk_fraction_transferred_to_actual_fill": True,
    "reward_fraction_transferred_to_actual_fill": True,
    "actual_fill_stop_target_recalculation_required": True,
    "complete_open_stock_position_coverage_required": True,
    "option_positions_fail_closed_v1": True,
    "horizon_sessions_preserved": True,
    "time_exit_trigger_enabled_v1": False,
    "price_exit_trigger_authority": False,
    "close_fill_authority": False,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
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
        RECURRENT_STOCK_EXIT_PLAN_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT = contract_fingerprint()
