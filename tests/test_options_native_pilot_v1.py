from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json

import pytest

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_plan_v1 import (
    OptionsNativePilotPlanError, build_options_native_pilot_plan, verify_options_native_pilot_plan,
)
from packages.performance.ledger import StrategyTrialLedger, StrategyTrialLedgerConflict
from packages.strategies.options_native_pilot_v1 import (
    OptionsNativePilotError, PriorEconomicLogReturnV1, SyntheticPilotVarianceInputV1,
    screen_synthetic_pilot_variance,
)
from packages.strategies.options_native_pilot_v1_contract import (
    DATA_FINGERPRINT, IMPLIED_INPUT_FINGERPRINT, SPECIFICATION_FINGERPRINT,
    pilot_data_contract, pilot_manifest, specification_trial_draft,
)
from scripts.plan_options_native_pilot_v1 import main


def fixture():
    decision = datetime(2022, 1, 10, 15, tzinfo=UTC)
    calendar = get_market_calendar("XNYS")
    days = calendar.sessions_in_range((decision - timedelta(days=75)).date(), decision.date())
    closes = [calendar.regular_open_close(day)[1] for day in days]
    closes = [at for at in closes if at < decision][-21:]
    returns = tuple(PriorEconomicLogReturnV1(start, end, end + timedelta(seconds=1),
                                             "0.02", "a" * 64)
                    for start, end in zip(closes, closes[1:]))
    return SyntheticPilotVarianceInputV1(
        feature_cutoff_utc=decision, model_maturity_utc=decision + timedelta(days=30),
        prior_returns=returns, call_iv="0.10", put_iv="0.10",
        implied_observed_at_utc=decision - timedelta(seconds=1),
        implied_available_at_utc=decision, implied_model_fingerprint=IMPLIED_INPUT_FINGERPRINT,
        source_integrity_qualified=True, availability_clocks_qualified=True,
        corporate_actions_qualified=True, rate_dividend_inputs_qualified=True,
    )


def test_specification_is_copy_isolated_bound_and_does_not_extend_legacy_directional_contract():
    from packages.execution.option_economics_contract import OPTION_ECONOMICS_CONTRACT
    spec = pilot_manifest()
    assert spec["construction"]["structure"] == "LONG_ATM_STRADDLE"
    assert spec["management"]["dynamic_exit"].startswith("forecast_total_variance <=")
    assert spec["research_protocol"]["maximum_strategy_variants"] == 1
    assert spec["research_protocol"]["positive_every_window_required"] is False
    assert spec["research_protocol"]["rolling_account_windows_sessions"] == [5, 21, 252]
    assert spec["data_contract_fingerprint"] == DATA_FINGERPRINT
    assert SPECIFICATION_FINGERPRINT == "e3ad55ad153ca61432bfde65aa0b5c54004766866a2919a567b6b5ade551efca"
    assert _fingerprint({k: v for k, v in spec.items() if k != "specification_fingerprint"}) == SPECIFICATION_FINGERPRINT
    spec["authority"]["live"] = True
    data = pilot_data_contract()
    data["option_pair_inputs"]["minimum_open_interest_each_leg"] = 0
    assert pilot_manifest()["authority"]["live"] is False
    assert pilot_data_contract()["option_pair_inputs"]["minimum_open_interest_each_leg"] == 100
    assert OPTION_ECONOMICS_CONTRACT["supported_structure"] == "LONG_SINGLE_LEG_CALL_OR_PUT_ONLY"


def test_plan_freezes_independent_both_rights_universe_and_protects_all_maturities():
    plan = build_options_native_pilot_plan()
    assert verify_options_native_pilot_plan(plan) == plan
    assert plan["planned_weekly_clocks"] == 418
    assert plan["entry_quote_surface_count"] == 411
    assert plan["scope_buffer_exclusions"] == 7
    requests = plan["entry_quote_surface_requests"]
    assert len({r["query_fingerprint"] for r in requests}) == 411
    assert all(r["params"]["right"] == "both" and r["params"]["symbol"] == "SPY" for r in requests)
    assert all(r["params"]["time_of_day"] == "10:00:00.000" for r in requests)
    assert requests[0]["params"]["start_date"] == "20180102"
    assert requests[-1]["params"]["start_date"] == "20251110"
    assert plan["by_year"]["2020"] == 52
    assert plan["reuse"]["legacy_9455_call_surface_plan_modified"] is False
    assert plan["later_demand"]["provider_specific_exact_requests_materialized"] is False
    assert plan["qualification_design"]["quote_requests_including_repeat"] == 25
    assert plan["qualification_design"]["total_initial_provider_request_design_cap"] == 64
    assert all(value is False or value == 0 for value in plan["authority"].values())
    assert plan["trial_registration"]["workstation_trial_ledger_appended"] is False


def test_calendar_plan_handles_holiday_first_session_dst_and_utc_clocks():
    rows = {r["date_et"]: r for r in build_options_native_pilot_plan()["rows"]}
    assert "2021-01-01" not in rows  # first session of that ISO week was in 2020
    assert rows["2021-01-19"]["feature_cutoff_utc"] == "2021-01-19T15:00:00+00:00"
    assert rows["2021-03-15"]["feature_cutoff_utc"] == "2021-03-15T14:00:00+00:00"
    assert rows["2021-03-08"]["order_eligible_utc"] == "2021-03-08T15:01:00+00:00"
    assert rows["2025-12-29"]["status"] == "EXCLUDED_BY_FROZEN_MATURITY_SCOPE_BUFFER"


@pytest.mark.parametrize("change", ["right", "clock", "authority", "specification", "row", "omission"])
def test_self_signed_changed_plans_do_not_pass_full_reconstruction(change):
    plan = build_options_native_pilot_plan()
    if change == "right":
        plan["entry_quote_surface_requests"][0]["params"]["right"] = "call"
    elif change == "clock":
        plan["entry_quote_surface_requests"][0]["params"]["time_of_day"] = "09:35:00.000"
    elif change == "authority":
        plan["authority"]["historical_replay_authority"] = True
    elif change == "specification":
        plan["specification"]["research_protocol"]["maximum_strategy_variants"] = 100
    elif change == "row":
        plan["rows"][0]["order_eligible_utc"] = "2026-01-01T00:00:00+00:00"
    else:
        del plan["rows"][0]
    plan["plan_fingerprint"] = _fingerprint({k: v for k, v in plan.items() if k != "plan_fingerprint"})
    with pytest.raises(OptionsNativePilotPlanError, match="drifted"):
        verify_options_native_pilot_plan(plan)


def test_variance_forecast_uses_only_prior_returns_and_the_same_explicit_maturity():
    inputs = fixture()
    report = screen_synthetic_pilot_variance(inputs)
    assert report["status"] == "FIXTURE_VARIANCE_FILTER_PASS"
    elapsed = Decimal(sum(int((item.interval_end_utc - item.interval_start_utc).total_seconds())
                          for item in inputs.prior_returns))
    expected = Decimal("0.008") / elapsed * Decimal(30 * 86400 - 60)
    assert Decimal(report["forecast_total_variance"]) == expected
    assert Decimal(report["implied_total_variance"]) == Decimal("0.01") * Decimal(30 * 86400 - 60) / Decimal(365 * 86400)
    doubled = screen_synthetic_pilot_variance(replace(inputs, model_maturity_utc=inputs.feature_cutoff_utc + timedelta(days=40)))
    assert Decimal(doubled["forecast_total_variance"]) > Decimal(report["forecast_total_variance"])
    assert doubled["status"] == report["status"]
    assert report["expected_dollar_profit"] is None and report["contracts_selected"] == 0
    assert report["historical_performance_evidence"] is False
    assert all(value is False or value == 0 for value in report["authority"].values())


def test_high_implied_variance_and_flat_return_history_abstain():
    inputs = fixture()
    high = screen_synthetic_pilot_variance(replace(inputs, call_iv="1.0", put_iv="1.0"))
    flat = screen_synthetic_pilot_variance(replace(inputs, prior_returns=tuple(
        replace(r, log_return="0") for r in inputs.prior_returns)))
    assert high["reasons"] == flat["reasons"] == ["NO_POSITIVE_FORECAST_VARIANCE_GAP"]
    assert Decimal(flat["forecast_total_variance"]) == 0


@pytest.mark.parametrize("field,reason", [
    ("source_integrity_qualified", "UNQUALIFIED_SOURCE"),
    ("availability_clocks_qualified", "UNQUALIFIED_AVAILABILITY_CLOCKS"),
    ("corporate_actions_qualified", "UNQUALIFIED_ECONOMIC_RETURN_ADJUSTMENTS"),
    ("rate_dividend_inputs_qualified", "UNQUALIFIED_RATE_DIVIDEND_INPUTS"),
])
def test_unknown_input_qualification_blocks_arithmetic_without_defaulting(field, reason):
    report = screen_synthetic_pilot_variance(replace(fixture(), **{field: False}))
    assert report["reasons"] == [reason]
    assert report["forecast_total_variance"] is report["implied_total_variance"] is None


@pytest.mark.parametrize("change,reason", [
    ({"implied_available_at_utc": fixture().feature_cutoff_utc + timedelta(seconds=61)}, "FUTURE_LATE_OR_STALE_IMPLIED_INPUT"),
    ({"implied_observed_at_utc": fixture().feature_cutoff_utc - timedelta(seconds=31)}, "FUTURE_LATE_OR_STALE_IMPLIED_INPUT"),
    ({"implied_observed_at_utc": fixture().feature_cutoff_utc + timedelta(seconds=1)}, "FUTURE_LATE_OR_STALE_IMPLIED_INPUT"),
    ({"implied_model_fingerprint": "0" * 64}, "IMPLIED_MODEL_CONTRACT_MISMATCH"),
])
def test_future_stale_or_wrong_model_inputs_cannot_make_earlier_features(change, reason):
    result = screen_synthetic_pilot_variance(replace(fixture(), **change))
    assert reason in result["reasons"]
    assert result["forecast_total_variance"] is None


def test_missing_duplicate_or_late_daily_return_cannot_shrink_or_move_the_window():
    inputs = fixture()
    for history, reason in (
        (inputs.prior_returns[:-1] + (inputs.prior_returns[-2],), "MISSING_DUPLICATE_OR_NONPRIOR_RETURN_WINDOW"),
        (inputs.prior_returns[:-1] + (replace(inputs.prior_returns[-1],
            available_at_utc=inputs.feature_cutoff_utc + timedelta(seconds=61)),), "FUTURE_OR_LATE_RETURN_INPUT"),
    ):
        result = screen_synthetic_pilot_variance(replace(inputs, prior_returns=history))
        assert reason in result["reasons"] and result["forecast_total_variance"] is None


@pytest.mark.parametrize("changes", [
    {"origin": "HISTORICAL_SOURCE"}, {"symbol": "QQQ"}, {"call_iv": "NaN"},
    {"call_iv": "-0.1"}, {"put_iv": "1e-9999999"}, {"put_iv": 0.2},
    {"rate_dividend_inputs_qualified": 1}, {"prior_returns": []},
    {"feature_cutoff_utc": datetime(2022, 1, 10, 15)},
    {"feature_cutoff_utc": datetime(2026, 1, 5, 15, tzinfo=UTC)},
    {"feature_cutoff_utc": datetime(2022, 1, 10, 15, 1, tzinfo=UTC)},
    {"feature_cutoff_utc": datetime(2022, 1, 9, 15, tzinfo=UTC)},
    {"model_maturity_utc": fixture().feature_cutoff_utc},
    {"model_maturity_utc": fixture().feature_cutoff_utc + timedelta(days=47)},
])
def test_malformed_or_out_of_scope_fixture_inputs_fail_closed(changes):
    with pytest.raises(OptionsNativePilotError):
        screen_synthetic_pilot_variance(replace(fixture(), **changes))


def test_registration_uses_existing_hash_chained_ledger_and_counts_one_specification(tmp_path):
    draft = specification_trial_draft(datetime(2026, 10, 16, 3, tzinfo=UTC))
    ledger = StrategyTrialLedger(tmp_path / "trials.jsonl")
    record = ledger.append(draft)
    assert ledger.read() == (record,)
    assert record.strategy_policy_fingerprint == SPECIFICATION_FINGERPRINT
    assert record.feature_fingerprint == DATA_FINGERPRINT
    assert record.performance_outcomes_opened is False
    assert record.master_protected_return_rows_read == 0
    with pytest.raises(StrategyTrialLedgerConflict):
        ledger.append(draft)


def test_publication_delay_can_use_readiness_minute_but_cannot_import_later_observations():
    inputs = fixture()
    report = screen_synthetic_pilot_variance(replace(inputs,
        implied_available_at_utc=inputs.feature_cutoff_utc + timedelta(seconds=30)))
    assert report["status"] == "FIXTURE_VARIANCE_FILTER_PASS"
    assert report["decision_ready_utc"] == "2022-01-10T15:01:00+00:00"
    later_observation = screen_synthetic_pilot_variance(replace(inputs,
        implied_observed_at_utc=inputs.feature_cutoff_utc + timedelta(seconds=1),
        implied_available_at_utc=inputs.feature_cutoff_utc + timedelta(seconds=30)))
    assert later_observation["reasons"] == ["FUTURE_LATE_OR_STALE_IMPLIED_INPUT"]


def test_cli_is_deterministic_and_never_overwrites_a_different_plan(tmp_path, capsys):
    target = tmp_path / "pilot.json"
    assert main(["--output", str(target), "--json"]) == 0
    original = target.read_bytes()
    assert json.loads(capsys.readouterr().out) == build_options_native_pilot_plan()
    assert main(["--output", str(target)]) == 0
    capsys.readouterr()
    assert target.read_bytes() == original
    target.write_text('{"original":"retain"}', encoding="utf-8")
    assert main(["--output", str(target)]) == 2
    assert target.read_text() == '{"original":"retain"}'
    assert main(["--output", str(tmp_path)]) == 2


def test_plan_and_fixture_screen_make_no_provider_or_source_file_reads(monkeypatch):
    from pathlib import Path
    from packages.providers.thetadata import client
    inputs = fixture()
    def forbidden(*args, **kwargs):
        pytest.fail("pilot specification work cannot contact providers or read source bodies")
    # Direct-library transport replaced the old REST get_json entry point.
    # Guard both the transport call and worker acquisition against accidental IO.
    monkeypatch.setattr(client, "_call", forbidden)
    monkeypatch.setattr(client, "_worker", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    plan = build_options_native_pilot_plan()
    report = screen_synthetic_pilot_variance(inputs)
    assert plan["authority"]["provider_requests"] == report["authority"]["provider_requests"] == 0
