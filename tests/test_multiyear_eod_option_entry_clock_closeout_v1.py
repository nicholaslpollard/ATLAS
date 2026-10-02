from __future__ import annotations

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_native_stock_open_v1 import CONTRACT as NATIVE_CONTRACT
from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    SCENARIO_CONTRACT as CONTINUOUS_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_eod_option_entry_clock_closeout_v1 import (
    build_eod_option_entry_clock_closeout,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)


def _signed(payload: dict, field: str) -> dict:
    value = dict(payload)
    value[field] = _fingerprint(value)
    return value


def _fixtures():
    native = _signed(
        {
            "contract": NATIVE_CONTRACT,
            "status": "MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY",
            "case_denominator": 3,
            "provider_requests": 0,
            "protected_outcomes_read": 0,
            "rows": [
                {
                    "case_id": "a",
                    "ticker": "ABC",
                    "signal_session": "2025-01-02",
                    "raw_underlying_price": "100",
                },
                {
                    "case_id": "b",
                    "ticker": "XYZ",
                    "signal_session": "2025-01-02",
                    "raw_underlying_price": "100",
                },
                {
                    "case_id": "c",
                    "ticker": "DEF",
                    "signal_session": "2025-01-02",
                    "raw_underlying_price": "50",
                },
            ],
        },
        "source_fingerprint",
    )
    base = _signed(
        {
            "contract": BASE_SCENARIO_CONTRACT,
            "native_source_fingerprint": native["source_fingerprint"],
            "original_case_denominator": 3,
            "provider_requests": 0,
            "protected_2026_outcomes_read": 0,
            "historical_account_pnl_authority": False,
            "cases": [
                {
                    "case_id": "a",
                    "year": "2025",
                    "ticker": "ABC",
                    "policy_id": "p1",
                    "signal_session": "2025-01-02",
                    "decision_at_utc": "2025-01-02T14:35:00+00:00",
                    "call": {
                        "status": "ENTRY_READY_MODELED_STANDARD_EOD",
                        "option_symbol": "ABC250221C00100000",
                        "entry": {
                            "at_utc": "2025-01-03T21:00:00+00:00",
                            "session_et": "2025-01-03",
                            "underlying_price_same_snapshot": "102",
                        },
                    },
                },
                {
                    "case_id": "b",
                    "year": "2025",
                    "ticker": "XYZ",
                    "policy_id": "p2",
                    "signal_session": "2025-01-02",
                    "decision_at_utc": "2025-01-02T14:35:00+00:00",
                    "call": {
                        "status": "ENTRY_READY_MODELED_STANDARD_EOD",
                        "option_symbol": "XYZ250221C00105000",
                        "entry": {
                            "at_utc": "2025-01-03T21:00:00+00:00",
                            "session_et": "2025-01-03",
                            "underlying_price_same_snapshot": "106",
                        },
                    },
                },
                {
                    "case_id": "c",
                    "year": "2025",
                    "ticker": "DEF",
                    "policy_id": "p3",
                    "signal_session": "2025-01-02",
                    "decision_at_utc": "2025-01-02T14:35:00+00:00",
                    "call": {"status": "ENTRY_SOURCE_NOT_CAUSALLY_READY"},
                },
            ],
        },
        "scenario_fingerprint",
    )
    continuous = _signed(
        {
            "contract": CONTINUOUS_SCENARIO_CONTRACT,
            "base_scenario_fingerprint": base["scenario_fingerprint"],
            "original_case_denominator": 3,
            "provider_requests": 0,
            "protected_2026_outcomes_read": 0,
            "historical_account_pnl_authority": False,
            "strategy_evidence_authority": False,
            "cases": [
                {
                    "case_id": "a",
                    "ticker": "ABC",
                    "signal_session": "2025-01-02",
                    "continuous_exit_policy": {
                        "stop_fraction": 0.03,
                        "target_fraction": 0.05,
                    },
                    "strategy_aligned_status":
                        "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY",
                },
                {
                    "case_id": "b",
                    "ticker": "XYZ",
                    "signal_session": "2025-01-02",
                    "continuous_exit_policy": {
                        "stop_fraction": 0.028,
                        "target_fraction": 0.05,
                    },
                    "strategy_aligned_status":
                        "STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY",
                },
                {
                    "case_id": "c",
                    "ticker": "DEF",
                    "signal_session": "2025-01-02",
                    "continuous_exit_policy": {
                        "stop_fraction": 0.03,
                        "target_fraction": 0.05,
                    },
                    "strategy_aligned_status":
                        "CALL_ENTRY_SOURCE_NOT_CAUSALLY_READY",
                },
            ],
        },
        "scenario_fingerprint",
    )
    return native, base, continuous


def test_closeout_reports_saturation_and_clock_translation():
    native, base, continuous = _fixtures()
    result = build_eod_option_entry_clock_closeout(native, base, continuous)

    assert result["continuous_v2"]["continuous_policy_cases"] == 3
    assert result["continuous_v2"]["stop_at_3pct_count"] == 2
    assert result["continuous_v2"]["target_at_5pct_count"] == 3
    assert result["continuous_v2"]["all_targets_at_upper_boundary"] is True

    clock = result["entry_clock_translation"]
    assert clock["causal_eod_call_entries"] == 2
    assert clock["stock_exit_not_after_option_entry"] == 1
    assert clock["stock_exit_not_after_option_entry_fraction"] == 0.5
    assert clock["source_ready_strategy_aligned_round_trips"] == 1
    assert clock["session_lag"]["median"] == 1.0
    assert clock["absolute_move_threshold_counts"]["ABS_MOVE_GTE_1PCT"]["count"] == 2
    assert clock["absolute_move_threshold_counts"]["ABS_MOVE_GTE_5PCT"]["count"] == 1
    assert clock["moneyness_at_raw_open"] == {"ATM": 1, "OTM": 1}
    assert clock["moneyness_at_option_entry"] == {"ITM": 2}
    assert clock["moneyness_changed"] == 2
    assert result["provider_requests"] == 0
    assert result["strategy_evidence_authority"] is False
