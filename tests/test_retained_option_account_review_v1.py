from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy
from packages.simulation.retained_option_account_review_v1 import (
    CLOSED, ENTRY, EXIT, FAILED_EXIT, OPEN, REPLAY_CONTRACT, SCENARIO_CONTRACT,
    RetainedOptionAccountBindingV1, RetainedOptionAccountReviewError,
    review_retained_option_account,
)


def signed(value, field):
    value = copy.deepcopy(value)
    value.pop(field, None)
    value[field] = _fingerprint(value)
    return value


def fixture(tmp_path):
    policy = ReplayPolicy(initial_cash="1000.00", max_open_positions=10)
    exit_policy = {"policy_id": "CONTINUOUS_DYNAMIC_EXIT_V2", "time_exit_sessions": 5, "case_specific_levels": True}
    cases = []
    for cid, ticker, status, at, exit_day in (
        ("closed", "AAA", "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY", "2022-03-03T21:00:00+00:00", "2022-03-08"),
        ("open", "BBB", "STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING", "2022-03-04T21:00:00+00:00", "2022-03-07"),
        ("not_ready", "CCC", "CALL_ENTRY_SOURCE_NOT_CAUSALLY_READY", None, None),
    ):
        cases.append({"case_id": cid, "year": "2022", "ticker": ticker, "economic_family_id": "family",
            "strategy_aligned_status": status,
            "stock_exit": {"session_et": exit_day, "disposition": "TIME_EXIT"} if exit_day else None,
            "call": {"option_symbol": f"{ticker}220318C00100000", "status": "ENTRY_READY_MODELED_STANDARD_EOD", "entry": {
                "at_utc": at, "ask_per_share": "2.00", "physical_quote_request_identity": "a" * 64,
                "physical_quote_body_sha256": "b" * 64}} if at else None,
            "strategy_exit_option_mark": {"bid_per_share": "1.00"} if cid == "closed" else None})
    scenario = signed({"contract": SCENARIO_CONTRACT,
        "status": "MODELED_CONTINUOUS_DYNAMIC_EXIT_V2_EOD_CALL_SCENARIO",
        "strategy_exit_policy": exit_policy, "safe_last_signal_session": "2025-12-23",
        "original_case_denominator": 3, "source_ready_strategy_aligned_round_trips": 1,
        "cases": cases, "by_status": {row["strategy_aligned_status"]: 1 for row in cases},
        "provider_requests": 0, "protected_2026_outcomes_read": 0, "historical_fills_verified": 0,
        "independent_occ_deliverable_multiplier_verified": 0,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "historical_account_pnl_authority": False, "strategy_evidence_authority": False,
        "future_option_exit_used_for_entry_admission": False}, "scenario_fingerprint")
    decisions = [{"case_id": row["case_id"], "year": "2022", "ticker": row["ticker"],
        "economic_family_id": "family", "strategy_aligned_status": row["strategy_aligned_status"],
        "account_status": CLOSED if row["case_id"] == "closed" else OPEN if row["case_id"] == "open" else row["strategy_aligned_status"],
        "contracts": 1 if row["case_id"] != "not_ready" else 0,
        "modeled_net_pnl": "-101.30" if row["case_id"] == "closed" else None,
        "entry_at_utc": row["call"]["entry"]["at_utc"] if row["call"] else None,
        "exit_at_utc": "2022-03-08T21:00:00+00:00" if row["case_id"] == "closed" else None} for row in cases]
    ledger = [
        {"kind": ENTRY, "case_id": "closed", "at_utc": "2022-03-03T21:00:00+00:00", "instrument": "AAA220318C00100000",
         "contracts": 1, "ask_per_share": "2.00", "cash_delta": "-200.65", "cash_after": "799.35", "exit_fees_reserved": "0.65"},
        {"kind": ENTRY, "case_id": "open", "at_utc": "2022-03-04T21:00:00+00:00", "instrument": "BBB220318C00100000",
         "contracts": 1, "ask_per_share": "2.00", "cash_delta": "-200.65", "cash_after": "598.70", "exit_fees_reserved": "1.30"},
        {"kind": FAILED_EXIT, "case_id": "open", "at_utc": "2022-03-07T21:00:00+00:00", "instrument": "BBB220318C00100000",
         "reason": "STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING", "cash_after": "598.70", "exit_fees_reserved": "1.30"},
        {"kind": EXIT, "case_id": "closed", "at_utc": "2022-03-08T21:00:00+00:00", "instrument": "AAA220318C00100000",
         "contracts": 1, "bid_per_share": "1.00", "cash_delta": "99.35", "cash_after": "698.05", "exit_fees_reserved": "0.65", "modeled_net_pnl": "-101.30"},
    ]
    yearly = {str(y): {"original_cases": 0, "statuses": {}} for y in range(2021, 2027)}
    yearly["2022"] = {"original_cases": 3, "statuses": {row["account_status"]: 1 for row in decisions}}
    replay = signed({"contract": REPLAY_CONTRACT, "status": "MODELED_STRATEGY_ALIGNED_EOD_CALL_ACCOUNT_NO_FILL_AUTHORITY",
        "scenario_fingerprint": scenario["scenario_fingerprint"], "strategy_exit_policy": exit_policy,
        "safe_last_signal_session": "2025-12-23", "policy": {name: getattr(policy, name) for name in policy.__dataclass_fields__},
        "max_positions_per_family": 3, "one_active_position_per_ticker": True,
        "original_case_denominator": 3, "source_ready_strategy_aligned_round_trips": 1,
        "admitted_positions": 2, "completed_round_trips": 1, "end_open_positions": 1, "peak_open_positions": 2,
        "initial_cash": "1000.00", "ending_cash": "698.05", "ending_equity": None,
        "modeled_realized_pnl": "-101.30", "modeled_cash_change": "-301.95", "modeled_total_return_if_fully_closed": None,
        "ending_reserved_exit_fees": "0.65", "rejections": {}, "by_year": yearly,
        "decisions": decisions, "ledger": ledger, "open_positions": [{"case_id": "open", "ticker": "BBB", "economic_family_id": "family",
            "symbol": "BBB220318C00100000", "contracts": 1, "entry_debit": "200.65", "entry_at_utc": "2022-03-04T21:00:00+00:00",
            "reserved_exit_fee": "0.65", "terminal_market_mark": None, "unrealized_pnl": None}],
        "provider_requests": 0, "protected_2026_outcomes_read": 0, "historical_fills_verified": 0,
        "independent_occ_deliverable_multiplier_verified": 0,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "future_option_exit_used_for_entry_admission": False, "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False, "paper": False, "live": False}, "replay_fingerprint")
    return persist(tmp_path, replay, scenario, policy)


def persist(tmp_path, replay, scenario, policy):
    binding = RetainedOptionAccountBindingV1(replay["replay_fingerprint"], scenario["scenario_fingerprint"],
        3, 1, 2, 1, 1, "698.05", "-101.30", policy)
    settings = SimpleNamespace(resolved_path=lambda rel: tmp_path / rel)
    for rel, report in ((binding.replay_relative_path, replay), (binding.scenario_relative_path, scenario)):
        target = settings.resolved_path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
    return settings, binding, replay, scenario


def test_readonly_review_reconciles_loss_open_cash_and_original_full_population(tmp_path):
    settings, binding, replay, scenario = fixture(tmp_path)
    paths = [settings.resolved_path(binding.replay_relative_path), settings.resolved_path(binding.scenario_relative_path)]
    original = [path.read_bytes() for path in paths]
    report = review_retained_option_account(settings, binding=binding)
    assert report["original_cases"] == 3 and report["admitted"] == 2
    assert report["completed"] == report["unresolved"] == 1
    assert report["modeled_realized_pnl"] == "-101.30"
    assert report["cash"] == "698.05"
    assert report["committed_open_entry_cash_including_fees"] == "200.65"
    assert report["cash_available_after_exit_fee_reserve"] == "697.40"
    assert report["equity"] is report["total_return"] is report["terminal_valuation_clock"] is None
    assert report["unresolved_by_entry_year"] == {"2022": 1}
    demand = report["unresolved_positions"][0]
    assert demand["option_symbol"] == "BBB220318C00100000" and demand["expiration"] == "2022-03-18"
    assert demand["settlement_inferred"] is demand["capital_release_authority"] is False
    assert report["simulations_run"] == report["raw_source_files_read"] == report["provider_requests"] == 0
    assert [path.read_bytes() for path in paths] == original


def test_signature_drift_and_wrong_run_prefix_fail_without_fallback(tmp_path):
    settings, binding, replay, scenario = fixture(tmp_path)
    path = settings.resolved_path(binding.replay_relative_path)
    replay["ending_cash"] = "999.99"
    path.write_text(json.dumps(replay))
    with pytest.raises(RetainedOptionAccountReviewError, match="identity/signature"):
        review_retained_option_account(settings, binding=binding)
    with pytest.raises(FileNotFoundError):
        review_retained_option_account(settings, binding=replace(binding, replay_identity="f" * 16))


@pytest.mark.parametrize("mutate,error", [
    (lambda r: r["ledger"][2].update(cash_delta="0.01"), "failed exit changed cash"),
    (lambda r: r["ledger"][0].update(cash_after="799.34"), "running balances"),
    (lambda r: r["ledger"].append(copy.deepcopy(r["ledger"][3])), "close without"),
    (lambda r: r["open_positions"][0].update(terminal_market_mark="0"), "unknown open economics"),
    (lambda r: r.update(ending_equity="698.05"), "equity or return"),
    (lambda r: r.update(historical_account_pnl_authority=True), "authority drifted"),
    (lambda r: r["by_year"]["2022"].update(original_cases=2), "annual account"),
    (lambda r: r["open_positions"][0].update(symbol="WRONG220318C00100000"), "OCC identity"),
    (lambda r: r["ledger"][0].update(at_utc="2026-01-02T21:00:00+00:00"), "2021-2025"),
    (lambda r: r["policy"].update(option_exit_fee_per_contract="0.00"), "cash/cost policy"),
])
def test_resigned_inconsistent_ledger_or_evidence_still_blocks(tmp_path, mutate, error):
    settings, binding, replay, scenario = fixture(tmp_path)
    mutate(replay)
    replay = signed(replay, "replay_fingerprint")
    settings, binding, _, _ = persist(tmp_path, replay, scenario, binding.policy)
    with pytest.raises(RetainedOptionAccountReviewError, match=error):
        review_retained_option_account(settings, binding=binding)


def test_reader_refuses_duplicate_json_and_oversized_artifact(tmp_path, monkeypatch):
    import packages.simulation.retained_option_account_review_v1 as module
    settings, binding, replay, scenario = fixture(tmp_path)
    path = settings.resolved_path(binding.replay_relative_path)
    original = path.read_text()
    path.write_text(original.replace('"ending_cash": "698.05"', '"ending_cash": "698.05", "ending_cash": "698.05"'))
    with pytest.raises(RetainedOptionAccountReviewError, match="duplicate JSON"):
        review_retained_option_account(settings, binding=binding)
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 10)
    with pytest.raises(RetainedOptionAccountReviewError, match="bound"):
        review_retained_option_account(settings, binding=binding)


def test_cli_saves_only_new_review_and_never_modifies_sources(tmp_path, monkeypatch, capsys):
    from scripts import review_retained_option_account_v1 as cli
    settings, binding, replay, scenario = fixture(tmp_path)
    settings.assert_external_storage_binding = lambda category: None
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(cli, "DEFAULT_BINDING", binding)
    monkeypatch.setattr(cli, "review_retained_option_account", lambda cfg: review_retained_option_account(cfg, binding=binding))
    original = settings.resolved_path(binding.replay_relative_path).read_bytes()
    assert cli.main(["--save-report"]) == 0
    saved = list((tmp_path / "data/research/retained_option_account_review_v1").glob("*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text())["equity"] is None
    assert settings.resolved_path(binding.replay_relative_path).read_bytes() == original
    assert "zero provider" in capsys.readouterr().out


def test_actual_existing_account_writer_shape_is_readable_without_new_simulation(tmp_path):
    from datetime import date
    from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
        StrategyExitPolicy, build_strategy_aligned_eod_option_scenario,
        replay_strategy_aligned_eod_call_account,
    )
    from tests.test_multiyear_strategy_aligned_eod_option_replay_v1 import fixture as source_fixture
    base, plan, handoff, daily, reader = source_fixture(exit_volume=0)
    # Generate only the existing two-case synthetic fixture, then audit its saved
    # writer shape. The operator path never calls either builder/replay function.
    scenario = build_strategy_aligned_eod_option_scenario(base, plan, handoff, daily,
        policy=StrategyExitPolicy(0.02, 0.05), safe_last_signal_session=date(2025, 12, 20),
        read_verified_body=reader, expected_original_cases=2)
    scenario.update(contract=SCENARIO_CONTRACT, status="MODELED_CONTINUOUS_DYNAMIC_EXIT_V2_EOD_CALL_SCENARIO",
                    strategy_exit_policy={"policy_id": "CONTINUOUS_DYNAMIC_EXIT_V2", "time_exit_sessions": 5, "case_specific_levels": True})
    scenario = signed(scenario, "scenario_fingerprint")
    policy = ReplayPolicy(max_open_positions=10)
    replay = replay_strategy_aligned_eod_call_account(scenario, policy=policy,
        expected_scenario_contract=SCENARIO_CONTRACT, replay_contract=REPLAY_CONTRACT)
    binding = RetainedOptionAccountBindingV1(replay["replay_fingerprint"], scenario["scenario_fingerprint"],
        2, 0, 1, 0, 1, replay["ending_cash"], replay["modeled_realized_pnl"], policy)
    settings = SimpleNamespace(resolved_path=lambda rel: tmp_path / rel)
    for rel, report in ((binding.replay_relative_path, replay), (binding.scenario_relative_path, scenario)):
        target = settings.resolved_path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, default=str))
    reviewed = review_retained_option_account(settings, binding=binding)
    assert reviewed["unresolved"] == 1 and reviewed["completed"] == 0
    assert reviewed["unresolved_by_reason"] == {"STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP": 1}
    assert reviewed["equity"] is None
