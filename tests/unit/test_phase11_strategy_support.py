from __future__ import annotations

from packages.backtesting.strategy_evaluation import StrategyEvaluationMetrics, StrategyEvaluationSummary
from packages.backtesting.strategy_support import StrategySupportStatus, classify_strategy_support


def _summary(strategy_id: str, mean: float | None, rows: int = 100) -> StrategyEvaluationSummary:
    metrics = StrategyEvaluationMetrics(
        rows=rows,
        mean_return=mean,
        median_return=mean,
        positive_rate=0.55 if mean is not None and mean > 0 else 0.45,
        stddev_return=0.02,
        p10_return=-0.01,
        p25_return=-0.005,
        p75_return=0.005,
        p90_return=0.01,
        worst_return=-0.05,
        best_return=0.05,
    )
    return StrategyEvaluationSummary(
        contract_version="test",
        strategy_id=strategy_id,
        direction="LONG",
        evaluation_start=None,
        evaluation_end=None,
        source_rows=rows,
        fired_rows=rows,
        routed_rows=rows,
        cost_grid_bps=(10.0,),
        aggregate_by_cost_bps={"10": metrics},
        by_year={},
        by_market_regime={},
    )


def test_support_requires_positive_overall_and_both_halves() -> None:
    decision = classify_strategy_support(
        development=_summary("s", 0.002),
        first_half=_summary("s", 0.001),
        second_half=_summary("s", 0.003),
    )
    assert decision.status == StrategySupportStatus.SUPPORTED
    assert decision.eligible_for_candidate_promotion is True


def test_positive_aggregate_with_unstable_half_is_mixed() -> None:
    decision = classify_strategy_support(
        development=_summary("s", 0.001),
        first_half=_summary("s", -0.001),
        second_half=_summary("s", 0.003),
    )
    assert decision.status == StrategySupportStatus.MIXED
    assert decision.eligible_for_candidate_promotion is False


def test_nonpositive_development_is_unsupported() -> None:
    decision = classify_strategy_support(
        development=_summary("s", 0.0),
        first_half=_summary("s", 0.001),
        second_half=_summary("s", 0.001),
    )
    assert decision.status == StrategySupportStatus.UNSUPPORTED


def test_empty_slice_is_insufficient() -> None:
    decision = classify_strategy_support(
        development=_summary("s", 0.001),
        first_half=_summary("s", None, rows=0),
        second_half=_summary("s", 0.001),
    )
    assert decision.status == StrategySupportStatus.INSUFFICIENT
