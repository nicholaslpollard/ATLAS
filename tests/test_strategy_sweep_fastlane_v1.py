from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import json

import pytest

from packages.simulation.multiyear_offline_account_replay_v1 import (
    ORIGIN, ReplayLeg, ReplaySignal,
)
from packages.simulation.strategy_sweep_fastlane_v1 import (
    FastlaneError, StrategyFixture, run_fixture_sweep,
)
from scripts.run_strategy_sweep_fastlane_v1 import (
    load_fixture_manifest, main,
)


def moment(hour: int, minute: int) -> datetime:
    return datetime(2025, 1, 6, hour, minute, tzinfo=UTC)


def stock_case(cid: str, *, exit_price: str | None = "110.00") -> ReplaySignal:
    return ReplaySignal(
        case_id=cid, year=2025, ticker="SPY",
        decision_at_utc=moment(14, 31),
        stock=ReplayLeg(
            symbol="SPY", kind="STOCK", entry_at_utc=moment(14, 36),
            exit_at_utc=moment(20, 0) if exit_price is not None else None,
            entry_per_share="100.00", exit_per_share=exit_price,
            multiplier=1, expiration=None, source_integrity_qualified=True,
            observation_clock_qualified=True, standard_deliverable_verified=True,
            exit_source_integrity_qualified=True if exit_price is not None else None,
            exit_observation_clock_qualified=True if exit_price is not None else None,
        ),
    )


def call_case(cid: str) -> ReplaySignal:
    return ReplaySignal(
        case_id=cid, year=2025, ticker="SPY", decision_at_utc=moment(14, 31),
        call=ReplayLeg(
            symbol="O:SPY250221C00500000", kind="CALL",
            entry_at_utc=moment(14, 36), exit_at_utc=moment(20, 0),
            entry_per_share="2.00", exit_per_share="3.00", multiplier=100,
            expiration=date(2025, 2, 21), source_integrity_qualified=True,
            observation_clock_qualified=True, standard_deliverable_verified=True,
            exit_source_integrity_qualified=True, exit_observation_clock_qualified=True,
        ),
    )


def one(cid: str = "caseA") -> list[StrategyFixture]:
    return [StrategyFixture("mean_reversion", "STOCK", (stock_case(cid),))]


def test_bounded_grid_reuses_same_cohort_and_reports_cost_sensitivity():
    result = run_fixture_sweep(one(), {
        "stock_slippage_bps": ["0", "100"],
        "max_open_positions": [1, 2],
    })
    assert result["scenario_count"] == 4
    assert result["provider_requests"] == result["broker_requests"] == 0
    assert not result["historical_performance_qualified"]
    assert result["combined_status"] == "SINGLE_STRATEGY_ONLY"
    means = {}
    for row in result["scenarios"]:
        assert row["individual"]["mean_reversion"]["ending_equity"] is not None
        assert row["individual"]["mean_reversion"]["synthetic_round_trips"] == 1
        means[row["policy_overrides"]["stock_slippage_bps"]] = Decimal(
            row["individual"]["mean_reversion"]["modeled_realized_pnl"]
        )
    assert means["0"] > means["100"]


def test_combined_uses_one_capital_account_not_sum_of_individuals():
    strategies = one("A") + [
        StrategyFixture("trend", "STOCK", (stock_case("B"),))
    ]
    result = run_fixture_sweep(strategies, {
        "max_open_positions": [1], "fraction_of_available_cash": ["0.10"],
    })
    row = result["scenarios"][0]
    assert row["individual"]["mean_reversion"]["synthetic_round_trips"] == 1
    assert row["individual"]["trend"]["synthetic_round_trips"] == 1
    assert row["combined_shared_capital"]["synthetic_round_trips"] == 1
    assert result["combined_status"] == "SAME_MODE_SHARED_CAPITAL_FIXTURE_ONLY"


def test_mixed_assets_are_tested_alone_but_never_fake_portfolio_netting():
    result = run_fixture_sweep(
        one() + [StrategyFixture("option", "CALL", (call_case("optionC"),))],
        {"option_slippage_per_share": ["0.00"]},
    )
    assert result["combined_status"] == "MIXED_ASSET_COMBINATION_NOT_QUALIFIED"
    assert "combined_shared_capital" not in result["scenarios"][0]
    assert result["scenarios"][0]["individual"]["option"]["synthetic_round_trips"] == 1


def test_unresolved_exits_have_null_equity_not_false_profit():
    result = run_fixture_sweep([
        StrategyFixture("unresolved", "STOCK", (stock_case("A", exit_price=None),))
    ], {"stock_slippage_bps": ["0"]})
    row = result["scenarios"][0]["individual"]["unresolved"]
    assert row["ending_equity"] is None
    assert row["open_positions"] == 1


def test_same_case_in_two_strategies_does_not_double_count_combined():
    with pytest.raises(FastlaneError, match="CROSS_STRATEGY_CASE_COLLISION"):
        run_fixture_sweep(one("A") + [
            StrategyFixture("trend", "STOCK", (stock_case("A"),))
        ], {"max_open_positions": [1]})


def test_fixture_only_and_grid_bounds_are_fail_closed():
    signal = stock_case("A")
    from dataclasses import replace
    with pytest.raises(FastlaneError, match="HISTORICAL_SOURCE_NOT_ADMITTED"):
        run_fixture_sweep([
            StrategyFixture("x", "STOCK", (replace(signal, origin="historical"),))
        ], {"max_open_positions": [1]})
    with pytest.raises(FastlaneError, match="TOO_MANY_SCENARIOS"):
        run_fixture_sweep(one(), {
            "fraction_of_available_cash": [str(i / 100) for i in range(1, 9)],
            "max_open_positions": list(range(1, 9)),
            "maximum_units_per_position": [1, 2],
        })
    with pytest.raises(FastlaneError, match="INVALID_POLICY_GRID"):
        run_fixture_sweep(one(), {"entry_threshold": [1]})


def _fixture_manifest() -> dict:
    return {
        "origin": ORIGIN,
        "policy_grid": {"stock_slippage_bps": ["0", "25"]},
        "strategies": [{
            "strategy_id": "mean_reversion", "mode": "STOCK",
            "signals": [{
                "case_id": "2025A", "year": 2025, "ticker": "SPY",
                "decision_at_utc": moment(14, 31).isoformat(),
                "stock": {
                    "symbol": "SPY", "kind": "STOCK",
                    "entry_at_utc": moment(14, 36).isoformat(),
                    "exit_at_utc": moment(20, 0).isoformat(),
                    "entry_per_share": "100.00", "exit_per_share": "110.00",
                    "multiplier": 1, "expiration": None,
                    "source_integrity_qualified": True,
                    "observation_clock_qualified": True,
                    "standard_deliverable_verified": True,
                    "exit_source_integrity_qualified": True,
                    "exit_observation_clock_qualified": True,
                },
            }],
        }],
    }


def test_cli_emits_hash_bound_diagnostic_and_refuses_report_overwrite(tmp_path):
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(_fixture_manifest()), encoding="utf-8")
    specs, grid = load_fixture_manifest(path)
    assert len(specs) == 1 and len(grid["stock_slippage_bps"]) == 2
    output = tmp_path / "report.json"
    assert main(["--manifest", str(path), "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "SYNTHETIC_DIAGNOSTIC_ONLY"
    assert report["scenario_count"] == 2
    assert main(["--manifest", str(path), "--output", str(output)]) == 2


def test_cli_rejects_historical_provenance_impersonation(tmp_path):
    data = _fixture_manifest()
    data["origin"] = "HISTORICAL"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FastlaneError, match="SYNTHETIC_FIXTURE_MANIFEST_REQUIRED"):
        load_fixture_manifest(path)
