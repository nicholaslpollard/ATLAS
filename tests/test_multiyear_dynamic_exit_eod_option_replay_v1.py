from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import packages.simulation.multiyear_dynamic_exit_eod_option_replay_v1 as mod
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.multiyear_dynamic_exit_eod_option_replay_v1 import (
    ABSTAIN_ACTION_ID,
    ASSIGNMENT_CONTRACT,
    SCENARIO_CONTRACT,
    build_bounded_dynamic_exit_assignments,
    build_paired_observation_diagnostics,
    combine_dynamic_action_scenarios,
)
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    SCENARIO_CONTRACT as STATIC_SCENARIO_CONTRACT,
)
from scripts.run_multiyear_dynamic_exit_eod_option_replay_v1 import (
    main as dynamic_option_runner_main,
)


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def fake_case(cid: str, fold: int, session: str):
    return SimpleNamespace(
        opportunity=SimpleNamespace(
            opportunity_id=cid,
            fold_id=fold,
            policy_id="p",
            economic_family_id="f",
            ticker="TEST",
            instrument_id="TEST",
            signal_session=date.fromisoformat(session),
            selector_score=1.0,
        )
    )


def test_bounded_assignments_freeze_current_fold_before_reveal(monkeypatch):
    cases = [
        fake_case("train", 1, "2020-12-01"),
        fake_case("a", 2, "2021-01-04"),
        fake_case("b", 2, "2021-01-05"),
        fake_case("c", 3, "2021-02-01"),
    ]
    seen = []

    def choose(*, cases, current_index, training_indexes, outcomes):
        current = cases[current_index]
        seen.append(
            (
                current.opportunity.opportunity_id,
                set(outcomes),
                tuple(training_indexes),
            )
        )
        return SimpleNamespace(
            action_id="ABSTAIN",
            stop_fraction=None,
            target_fraction=None,
            fallback_level=None,
            context_dimensions=(),
            context_key=(),
            training_cases=0,
            training_sessions=0,
            training_instruments=0,
            training_fold_min=None,
            training_fold_max=None,
            training_cutoff_session=None,
            selected_lcb_net_return=None,
            selected_mean_trade_net_return=None,
            selected_probability_positive=None,
            reason="TEST",
        )

    def reveal(cases, indexes, outcomes):
        for index in indexes:
            outcomes[(index, "revealed")] = 1.0

    monkeypatch.setattr(mod, "_choose_action", choose)
    monkeypatch.setattr(mod, "_reveal_action_outcomes", reveal)

    result = build_bounded_dynamic_exit_assignments(
        cases,
        target_start=date(2021, 1, 1),
        safe_end=date(2021, 12, 31),
    )

    observations = {cid: outcomes for cid, outcomes, _ in seen}
    # Neither case in fold 2 may see either fold-2 outcome.
    assert all(key[0] == 0 for key in observations["a"])
    assert all(key[0] == 0 for key in observations["b"])
    # Fold 3 may see folds 1 and 2 after fold 2 was completely assigned.
    assert {key[0] for key in observations["c"]} == {0, 1, 2}
    assert result["current_fold_outcomes_used_for_selection"] is False
    assert result["protected_2026_outcomes_read"] == 0


def base_scenario():
    return signed({
        "contract": "atlas-multiyear-historical-eod-option-scenario-v1",
        "status": "MODELED_HISTORICAL_EOD_OPTION_SCENARIO_NO_FILL_AUTHORITY",
        "original_case_denominator": 3,
        "quote_plan_fingerprint": "q" * 64,
        "handoff_fingerprint": "h" * 64,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "future_exit_used_for_entry_admission": False,
        "cases": [
            {
                "case_id": "selected",
                "year": "2022",
                "ticker": "TEST",
                "policy_id": "p",
                "signal_session": "2022-01-03",
                "decision_at_utc": "2022-01-04T14:35:00+00:00",
                "call": {
                    "status": "ENTRY_READY_MODELED_STANDARD_EOD",
                    "entry": {
                        "session_et": "2022-01-05",
                        "ask_per_share": "1.00",
                    },
                },
                "put": None,
            },
            {
                "case_id": "abstain",
                "year": "2022",
                "ticker": "TEST2",
                "policy_id": "p",
                "signal_session": "2022-01-03",
                "decision_at_utc": "2022-01-04T14:35:00+00:00",
                "call": None,
                "put": None,
            },
            {
                "case_id": "tail",
                "year": "2025",
                "ticker": "TEST3",
                "policy_id": "p",
                "signal_session": "2025-12-24",
                "decision_at_utc": "2025-12-26T14:35:00+00:00",
                "call": None,
                "put": None,
            },
        ],
    }, "scenario_fingerprint")


def static_action_scenario(base):
    cases = [
        {
            "case_id": "selected",
            "year": "2022",
            "ticker": "TEST",
            "policy_id": "p",
            "signal_session": "2022-01-03",
            "decision_at_utc": "2022-01-04T14:35:00+00:00",
            "strategy_exit_policy": {
                "policy_id": "STOP_02PCT_TARGET_05PCT",
                "stop_fraction": 0.02,
                "target_fraction": 0.05,
            },
            "economic_family_id": "f",
            "selector_score": 1.0,
            "stock_exit": {
                "disposition": "TIME",
                "session_offset": 5,
                "session_et": "2022-01-11",
            },
            "call": {
                "status": "ENTRY_READY_MODELED_STANDARD_EOD",
                "entry": {
                    "session_et": "2022-01-05",
                    "ask_per_share": "1.00",
                },
            },
            "strategy_aligned_status":
                "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY",
            "strategy_exit_option_mark": {
                "session_et": "2022-01-11",
                "bid_per_share": "1.30",
            },
            "future_option_exit_used_for_entry_admission": False,
            "protected_2026_outcomes_read": 0,
        },
        {
            "case_id": "abstain",
            "year": "2022",
            "ticker": "TEST2",
            "policy_id": "p",
            "signal_session": "2022-01-03",
            "decision_at_utc": "2022-01-04T14:35:00+00:00",
            "strategy_exit_policy": {},
            "economic_family_id": "f",
            "selector_score": 1.0,
            "stock_exit": None,
            "call": None,
            "strategy_aligned_status": "NO_DATED_CALL_RIGHT",
            "strategy_exit_option_mark": None,
            "future_option_exit_used_for_entry_admission": False,
            "protected_2026_outcomes_read": 0,
        },
        {
            "case_id": "tail",
            "year": "2025",
            "ticker": "TEST3",
            "policy_id": "p",
            "signal_session": "2025-12-24",
            "decision_at_utc": "2025-12-26T14:35:00+00:00",
            "strategy_exit_policy": {},
            "economic_family_id": "f",
            "selector_score": 1.0,
            "stock_exit": None,
            "call": None,
            "strategy_aligned_status": "PROTECTED_2026_STOCK_HORIZON_WITHHELD",
            "strategy_exit_option_mark": None,
            "future_option_exit_used_for_entry_admission": False,
            "protected_2026_outcomes_read": 0,
        },
    ]
    return signed({
        "contract": STATIC_SCENARIO_CONTRACT,
        "status": "MODELED_STRATEGY_ALIGNED_EOD_CALL_SCENARIO_NO_FILL_AUTHORITY",
        "base_scenario_fingerprint": base["scenario_fingerprint"],
        "original_case_denominator": 3,
        "safe_last_signal_session": "2025-12-23",
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "cases": cases,
    }, "scenario_fingerprint")


def assignments():
    return signed({
        "contract": ASSIGNMENT_CONTRACT,
        "status": "BOUNDED_DYNAMIC_EXIT_V1_ASSIGNMENTS_NO_2026_OUTCOMES",
        "source_dynamic_exit_contract_fingerprint": "d" * 64,
        "target_assignment_cases": 2,
        "selected_cases": 1,
        "abstained_cases": 1,
        "current_case_future_path_used_for_selection": False,
        "current_fold_outcomes_used_for_selection": False,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "strategy_evidence_authority": False,
        "rows": [
            {
                "opportunity_id": "selected",
                "economic_family_id": "f",
                "selector_score": 1.0,
                "action_id": "STOP_02_TARGET_05",
                "stop_fraction": 0.02,
                "target_fraction": 0.05,
                "reason": "HIGHEST_POSITIVE_SUPPORTED_ROBUST_LCB",
            },
            {
                "opportunity_id": "abstain",
                "economic_family_id": "f",
                "selector_score": 1.0,
                "action_id": ABSTAIN_ACTION_ID,
                "stop_fraction": None,
                "target_fraction": None,
                "reason": "NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB",
            },
        ],
    }, "assignment_fingerprint")


def test_dynamic_combination_preserves_abstain_and_protected_tail():
    base = base_scenario()
    combined = combine_dynamic_action_scenarios(
        base,
        assignments(),
        {"STOP_02_TARGET_05": static_action_scenario(base)},
        safe_last_signal_session=date(2025, 12, 23),
    )
    assert combined["contract"] == SCENARIO_CONTRACT
    rows = {row["case_id"]: row for row in combined["cases"]}
    assert (
        rows["selected"]["strategy_aligned_status"]
        == "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
    )
    assert rows["selected"]["dynamic_assignment"]["action_id"] == "STOP_02_TARGET_05"
    assert rows["abstain"]["strategy_aligned_status"] == "DYNAMIC_EXIT_ABSTAIN"
    assert (
        rows["tail"]["strategy_aligned_status"]
        == "PROTECTED_2026_STOCK_HORIZON_WITHHELD"
    )
    assert combined["dynamic_selected_cases"] == 1
    assert combined["dynamic_abstained_cases"] == 1
    assert combined["protected_2026_outcomes_read"] == 0


def test_paired_diagnostic_is_explicitly_noncausal_portfolio():
    base = base_scenario()
    combined = combine_dynamic_action_scenarios(
        base,
        assignments(),
        {"STOP_02_TARGET_05": static_action_scenario(base)},
        safe_last_signal_session=date(2025, 12, 23),
    )
    report = build_paired_observation_diagnostics(combined)
    assert report["overall"]["pairs"] == 1
    assert report["overall"]["mean_net_pnl_per_contract"] == 28.7
    assert report["conditioning_on_future_exit_source"] is True
    assert report["causal_portfolio_result"] is False
    assert report["historical_account_pnl_authority"] is False
    assert report["strategy_evidence_authority"] is False


def test_dynamic_option_runner_imports_end_to_end():
    assert callable(dynamic_option_runner_main)
