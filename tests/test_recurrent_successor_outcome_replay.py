from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import packages.backtesting.recurrent_successor_outcome_replay as replay
from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
)
from packages.backtesting.recurrent_successor_outcome_replay_contract import (
    AUTHORITY,
    RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT,
    recurrent_successor_outcome_replay_manifest,
)


def _primary_net(gross: float, cost_bps: float) -> float:
    half = cost_bps / 20_000.0
    return (100.0 * (1.0 + gross) * (1.0 - half) - 100.0 * (1.0 + half)) / 100.0


def _opportunity(*, direction: str = "LONG", gross: float = 0.02) -> SelectedReplayOpportunity:
    return SelectedReplayOpportunity(
        opportunity_id=("1" if direction == "LONG" else "2") * 64,
        fold_id=1,
        policy_id="synthetic_policy_v1",
        economic_family_id="synthetic_family",
        native_timeframe="1d",
        instrument_id="SYNTH",
        ticker="SYNTH",
        signal_session=date(2024, 1, 2),
        direction=direction,
        fallback_level=5,
        selector_score=0.005,
        primary_net_return=_primary_net(gross, 10.0),
        gross_return=gross,
        liquidity_bucket="GE_250M",
        decision_utc=datetime(2024, 1, 2, 21, 0, tzinfo=UTC),
        entry_utc=datetime(2024, 1, 3, 14, 30, tzinfo=UTC),
        exit_utc=datetime(2024, 1, 9, 21, 0, tzinfo=UTC),
        round_trip_cost_bps=10.0,
        training_start=date(2022, 1, 3),
        training_end=date(2023, 12, 29),
        training_sample_size=200,
        training_mean_gross_return=0.02,
        training_p10_gross_return=-0.01,
        training_p25_gross_return=0.005,
        training_median_gross_return=0.015,
        training_p75_gross_return=0.03,
        training_p90_gross_return=0.05,
        training_probability_positive_gross=0.70,
        training_probability_positive_net=0.65,
        training_mean_mfe=0.04,
        training_mean_mae=0.02,
        training_max_abs_excursion=0.08,
        training_median_holding_minutes=None,
        source_analysis_fingerprint="a" * 64,
    )


def test_contract_is_research_only_and_self_fingerprinted() -> None:
    manifest = recurrent_successor_outcome_replay_manifest()
    assert manifest["fingerprint"] == RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["provider_calls_permitted"] == 0
    assert AUTHORITY["broker_reads_permitted"] == 0
    assert AUTHORITY["broker_writes_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["strategy_promotion"] is False


def test_training_forecast_does_not_depend_on_test_outcome() -> None:
    base = _opportunity(gross=0.02)
    changed_outcome = replace(
        base,
        gross_return=-0.40,
        primary_net_return=_primary_net(-0.40, 10.0),
    )
    first = replay._training_forecast(base)
    second = replay._training_forecast(changed_outcome)
    assert first == second
    assert first.evidence_cutoff_utc < first.forecast_created_utc
    assert first.sample_size == 200
    assert first.mean_signed_return == pytest.approx(0.02)


def test_recurrent_outcome_replay_reproduces_primary_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_opportunity = _opportunity(direction="LONG", gross=0.02)
    short_opportunity = replace(
        _opportunity(direction="SHORT", gross=0.01),
        instrument_id="SHORTY",
        ticker="SHORTY",
        opportunity_id="2" * 64,
    )
    source = {
        "conditioning_root": str(tmp_path / "conditioning"),
        "conditioning_analysis_fingerprint": "a" * 64,
        "source_integrity_fingerprint": "b" * 64,
        "selected_opportunity_count": 2,
        "duckdb_threads": 1,
    }

    def fake_loader(*args, **kwargs):
        return (long_opportunity, short_opportunity), source

    monkeypatch.setattr(
        replay,
        "load_selected_replay_opportunities",
        fake_loader,
    )

    report = replay.run_recurrent_successor_outcome_replay(
        tmp_path,
        initial_equity=100_000.0,
        start_session=date(2024, 1, 2),
        end_session=date(2024, 1, 2),
        output_root=tmp_path / "out",
    )

    expected_trade_pnl = 10_000.0 * long_opportunity.primary_net_return
    assert report["selected_opportunities"] == 2
    assert report["supported_long_selected"] == 1
    assert report["unsupported_short_selected"] == 1
    assert report["admitted_positions"] == 1
    assert report["completed_positions"] == 1
    assert report["peak_active_or_reserved_slots"] == 1
    assert float(report["final_book_equity"]) == pytest.approx(
        100_000.0 + expected_trade_pnl
    )
    assert float(report["total_return_on_initial_equity"]) == pytest.approx(
        expected_trade_pnl / 100_000.0
    )
    assert report["interpretation"]["future_outcome_used_for_admission"] is False
    assert report["interpretation"]["bar_level_stop_target_time_retest"] is False

    summary = tmp_path / "out" / "run_summary.json"
    trades = tmp_path / "out" / "closed_trades.jsonl"
    assert summary.is_file()
    assert trades.is_file()
    assert len(trades.read_text(encoding="utf-8").strip().splitlines()) == 1
