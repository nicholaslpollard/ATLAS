from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from packages.backtesting.reference_strategy_runner import (
    ProtectedMasterWindowError,
    ReferenceStrategyHistoricalRunner,
    plan_reference_trade,
    reference_input_fingerprint,
    simulate_reference_trade,
)
from packages.schemas.strategy_lab import (
    OpportunityDisposition,
    OpportunityOutcomeStatus,
    ReferenceExitReason,
)
from packages.strategies.reference_library import REFERENCE_STRATEGY_CATALOG


def _simulation_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session_date": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)],
            "open": [99.0, 100.0, 101.0],
            "high": [100.0, 110.0, 102.0],
            "low": [98.0, 96.0, 99.0],
            "close": [99.0, 101.0, 100.0],
            "atr_14": [2.0, 2.0, 2.0],
            "macd_signal_cross_up": [1.0, 0.0, 0.0],
            "macd_signal_cross_down": [0.0, 0.0, 0.0],
        }
    )


def _daily_frame(closes: list[float]) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02", periods=len(closes), freq="B", tz="UTC")
    high = [value + 1.0 for value in closes]
    low = [value - 1.0 for value in closes]
    if len(closes) > 201:
        low[201] = 150.0
    return pd.DataFrame(
        {
            "instrument_id": "figi:TEST",
            "ticker": "TEST",
            "session_date": timestamps.date,
            "timestamp_utc": timestamps,
            "open": closes,
            "high": high,
            "low": low,
            "close": closes,
            "volume": 100_000.0,
            "pit_active": True,
            "security_type": "CS",
            "identity_clear": True,
            "price_adjustment_mode": "SPLIT_ADJUSTED",
            "raw_price_lineage_id": "raw-bars-v1",
        }
    )


def test_plan_enters_next_open_and_collision_exits_adverse_first() -> None:
    specification = REFERENCE_STRATEGY_CATALOG.get("macd_shift_12_26_9_long_v1")
    frame = _simulation_frame()
    plan, reasons = plan_reference_trade(specification, frame, 0)
    assert plan is not None
    assert plan.entry_position == 1
    assert plan.entry_price == 100.0
    assert plan.initial_stop_price == 97.0
    assert plan.target_price == 109.0
    assert "PLAN_NEXT_REGULAR_SESSION_OPEN" in reasons

    result = simulate_reference_trade(specification, frame, plan)
    assert result.outcome_status == OpportunityOutcomeStatus.EXITED
    assert result.exit_reason == ReferenceExitReason.INITIAL_OR_TRAILING_STOP
    assert result.exit_price == 97.0
    assert result.exit_at_session_open is False
    assert result.holding_sessions == 1
    assert result.same_bar_collision_adverse_first is True
    assert result.gross_directional_return == pytest.approx(-0.03)
    assert result.primary_net_directional_return == pytest.approx(-0.031)


def test_indicator_exit_uses_next_open_and_counts_exposure_sessions() -> None:
    specification = REFERENCE_STRATEGY_CATALOG.get("macd_shift_12_26_9_long_v1")
    frame = _simulation_frame()
    frame.loc[1, ["high", "low", "macd_signal_cross_down"]] = [102.0, 99.0, 1.0]
    plan, _ = plan_reference_trade(specification, frame, 0)
    assert plan is not None

    result = simulate_reference_trade(specification, frame, plan)
    assert result.exit_reason == ReferenceExitReason.MACD_OPPOSITE_CROSS
    assert result.exit_price == 101.0
    assert result.exit_at_session_open is True
    assert result.holding_sessions == 1


def test_runner_rejects_retained_master_protected_window_before_feature_work() -> None:
    frame = pd.DataFrame({"session_date": [date(2026, 6, 1)]})
    with pytest.raises(ProtectedMasterWindowError, match="master protected window"):
        ReferenceStrategyHistoricalRunner().run(frame)


def test_runner_records_selected_opportunity_and_is_deterministic() -> None:
    closes = [100.0] * 200 + [200.0, 200.0, 190.0]
    frame = _daily_frame(closes)
    runner = ReferenceStrategyHistoricalRunner()
    first = runner.run(frame)
    second = runner.run(frame)
    assert first.run_fingerprint == second.run_fingerprint
    assert first.input_fingerprint == reference_input_fingerprint(frame)
    assert first.protected_master_return_rows_read == 0
    assert first.broker_writes == first.paper_submits == first.live_writes == 0

    rows = [
        item
        for item in first.opportunities
        if item.strategy_id == "ma_trend_cross_50_200_long_v1"
    ]
    assert len(rows) == 1
    opportunity = rows[0]
    assert opportunity.disposition == OpportunityDisposition.SELECTED_INDEPENDENT_REPLAY
    assert opportunity.signal_session == frame.loc[200, "session_date"]
    assert opportunity.entry_session == frame.loc[201, "session_date"]
    assert opportunity.outcome_status == OpportunityOutcomeStatus.EXITED
    assert opportunity.exit_reason == ReferenceExitReason.INITIAL_OR_TRAILING_STOP
    assert opportunity.counterfactual_only is False
