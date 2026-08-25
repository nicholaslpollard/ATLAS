from __future__ import annotations

from datetime import date, timedelta

from packages.backtesting.phase24_gate1_policy import PHASE24_GATE1_CHALLENGER_VARIANTS
from packages.backtesting.phase24_gate2 import (
    SessionSignal,
    build_challenger_registry,
    chronological_boundaries,
    holm_bonferroni,
    internal_checks,
    selection_checks,
    tranche_metrics,
)


def test_gate2_builds_exact_preregistered_challenger_registry() -> None:
    registry = build_challenger_registry()
    assert len(registry.all()) == len(PHASE24_GATE1_CHALLENGER_VARIANTS) == 28
    momentum = registry.get("momentum_long_v2_rsi60")
    by_reason = {item.reason_code: item for item in momentum.conditions}
    assert by_reason["rsi_above_midline"].right_value == 60.0
    trend = registry.get("trend_following_long_v2_rsi55_rvol1")
    reasons = {item.reason_code for item in trend.conditions}
    assert "phase24_rsi_above_55" in reasons
    assert "phase24_rvol_above_1" in reasons


def test_gate2_chronological_split_locks_selection_purge_internal_order() -> None:
    start = date(2020, 1, 1)
    sessions = tuple(start + timedelta(days=index) for index in range(100))
    boundaries = chronological_boundaries(sessions)
    assert boundaries.selection_session_count == 75
    assert len(boundaries.purged_sessions) == 3
    assert boundaries.internal_session_count == 22
    assert boundaries.selection_end < boundaries.purged_sessions[0]
    assert boundaries.purged_sessions[-1] < boundaries.internal_start


def test_gate2_session_block_metrics_and_gates_are_deterministic() -> None:
    start = date(2018, 1, 1)
    signals = tuple(
        SessionSignal(
            session_date=start + timedelta(days=index),
            regime="BULL",
            raw_rows=10,
            gross_mean_return=0.01,
        )
        for index in range(300)
    )
    first = tranche_metrics(signals, confidence=0.95, folds=6, label="unit-positive")
    second = tranche_metrics(signals, confidence=0.95, folds=6, label="unit-positive")
    assert first == second
    assert first.primary_lcb is not None and first.primary_lcb > 0.0
    assert first.primary_bootstrap_p_value is not None and first.primary_bootstrap_p_value < 0.01
    assert first.stress_mean_return is not None and first.stress_mean_return > 0.0
    assert all(selection_checks(first).values())

    internal_signals = signals[:100]
    internal = tranche_metrics(internal_signals, confidence=0.90, folds=3, label="unit-internal")
    assert all(internal_checks(internal).values())


def test_gate2_holm_bonferroni_is_step_down_and_fail_closed_after_first_miss() -> None:
    result = holm_bonferroni(
        {"a": 0.001, "b": 0.02, "c": 0.03, "d": 0.04},
        alpha=0.05,
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is False
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False
