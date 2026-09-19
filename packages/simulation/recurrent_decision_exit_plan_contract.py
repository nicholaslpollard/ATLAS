from __future__ import annotations

import hashlib
import json


RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-decision-stock-exit-plan-v1",
    "scope": (
        "PRODUCT_SIMULATION_DECISION_RECORD_TO_DURABLE_OPEN_STOCK_EXIT_PLAN_BOOK"
    ),
    "source_decision_record_contract_required": True,
    "source_forecast_contract_required": True,
    "source_open_position_required": True,
    "source_recurrent_state_binding_required": True,
    "bullish_stock_long_only_v1": True,
    "option_positions_fail_closed_v1": True,
    "explicit_exit_policy_required": True,
    "stop_threshold_must_exist_in_forecast": True,
    "target_threshold_must_exist_in_forecast": True,
    "stop_and_target_thresholds_may_differ": True,
    "actual_entry_fill_binding_required": True,
    "stop_price_derived_from_actual_fill": True,
    "target_price_derived_from_actual_fill": True,
    "forecast_horizon_preserved": True,
    "time_exit_trigger_enabled_v1": False,
    "full_decision_record_retained_per_open_position": True,
    "existing_open_position_plans_immutable": True,
    "new_positions_require_current_reserve_decision_evidence": True,
    "exact_open_position_plan_coverage_required": True,
    "closed_position_plans_pruned_on_rebuild": True,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "price_trigger_authority": False,
    "close_fill_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
