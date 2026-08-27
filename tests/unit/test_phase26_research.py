from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from packages.backtesting.phase26_research import (
    chronological_boundaries,
    development_research_checks,
    holm_bonferroni,
    selection_checks,
    tranche_metrics,
)


def _trading_dates(count: int) -> list[date]:
    start = date(2024, 1, 2)
    return [start + timedelta(days=index) for index in range(count)]


def test_phase26_boundaries_use_selection_then_exact_three_session_purge() -> None:
    sessions = _trading_dates(100)
    boundaries = chronological_boundaries(sessions)
    assert boundaries.selection_session_count == 75
    assert boundaries.purged_sessions == tuple(sessions[75:78])
    assert boundaries.internal_start == sessions[78]
    assert boundaries.internal_session_count == 22


def test_phase26_metrics_aggregate_same_session_rows_before_confidence_statistics() -> None:
    dates = _trading_dates(30)
    rows: list[dict[str, object]] = []
    # Ten correlated rows on day one should still count as one confidence session.
    for index in range(10):
        rows.append(
            {
                "as_of_date": dates[0],
                "directional_return": 0.05,
                "market_state": "RISK_ON",
                "effective_ticker_state": "UPTREND",
                "instrument_id": f"A{index}",
            }
        )
    for index, session in enumerate(dates[1:], start=1):
        rows.append(
            {
                "as_of_date": session,
                "directional_return": 0.01,
                "market_state": "RISK_ON",
                "effective_ticker_state": "UPTREND",
                "instrument_id": f"B{index}",
            }
        )
    metrics = tranche_metrics(
        pd.DataFrame(rows), confidence=0.90, folds=3, label="unit-session-dependence"
    )
    assert metrics.raw_rows == 39
    assert metrics.signal_sessions == 30
    assert metrics.max_single_session_row_fraction == 10 / 39


def test_phase26_win_rate_and_median_are_diagnostics_not_selection_vetoes() -> None:
    # Construct 300 sessions with a 40% trade win rate but positive expectancy.
    dates = _trading_dates(300)
    rows = []
    for index, session in enumerate(dates):
        value = 0.03 if index % 5 in (0, 1) else -0.005
        rows.append(
            {
                "as_of_date": session,
                "directional_return": value,
                "market_state": "RISK_ON" if index < 150 else "RANGE",
                "effective_ticker_state": "UPTREND" if index < 150 else "MIXED",
            }
        )
    metrics = tranche_metrics(
        pd.DataFrame(rows), confidence=0.90, folds=6, label="unit-positive-expectancy"
    )
    checks = selection_checks(metrics)
    assert metrics.primary_trade_win_rate is not None
    assert metrics.primary_trade_win_rate < 0.50
    assert "primary_trade_win_rate" not in checks
    assert "primary_median_trade_return" not in checks
    assert checks["primary_mean_positive"] is True
    assert checks["stress_mean_positive"] is True


def test_phase26_holm_is_global_and_step_down() -> None:
    result = holm_bonferroni(
        {"a": 0.001, "b": 0.01, "c": 0.02, "d": 0.50}, alpha=0.05
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["c"]["rejected_null"] is True
    assert result["d"]["rejected_null"] is False


def test_phase26_development_stage_can_pass_only_while_protected_returns_are_unread() -> None:
    holm = {f"candidate-{index}": {} for index in range(24)}
    checks = development_research_checks(
        observation_report={"pass": True, "protected_return_reads": 0},
        holm=holm,
        selected_ids=(),
        internal_metrics={},
        finalist_ids=(),
        finalist_payload={"protected_returns_read": 0},
    )
    assert all(checks.values())
    assert "protected_returns_read" not in checks

    observation_leak = development_research_checks(
        observation_report={"pass": True, "protected_return_reads": 1},
        holm=holm,
        selected_ids=(),
        internal_metrics={},
        finalist_ids=(),
        finalist_payload={"protected_returns_read": 0},
    )
    assert observation_leak["protected_returns_unread"] is False

    finalist_leak = development_research_checks(
        observation_report={"pass": True, "protected_return_reads": 0},
        holm=holm,
        selected_ids=(),
        internal_metrics={},
        finalist_ids=(),
        finalist_payload={"protected_returns_read": 1},
    )
    assert finalist_leak["finalist_artifact_protected_returns_unread"] is False
