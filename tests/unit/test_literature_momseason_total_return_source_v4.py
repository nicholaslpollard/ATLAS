from packages.backtesting.literature_momseason_total_return_source_v4 import (
    MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR,
    MOMSEASON_MASSIVE_USD_DIVIDEND_SCALE_MAX_RELATIVE_ERROR,
    MOMSEASON_MIN_MASSIVE_USD_DIVIDEND_CASES,
    MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR,
    _metric,
    _metric_pass,
)


def test_v4_reuses_tight_source_semantics_tolerances() -> None:
    assert MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR == 0.001
    assert MOMSEASON_MASSIVE_USD_DIVIDEND_SCALE_MAX_RELATIVE_ERROR == 0.001
    assert MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR == 0.001
    assert MOMSEASON_MIN_MASSIVE_USD_DIVIDEND_CASES == 3


def test_metric_pass_requires_minimum_evidence_count() -> None:
    metric = _metric([0.0001, 0.0002])
    assert _metric_pass(metric, threshold=0.001, minimum_count=3) is False


def test_metric_pass_rejects_material_error() -> None:
    metric = _metric([0.0001, 0.0002, 0.0011])
    assert _metric_pass(metric, threshold=0.001, minimum_count=3) is False


def test_metric_pass_accepts_sufficient_tight_evidence() -> None:
    metric = _metric([0.0001, 0.0002, 0.0003])
    assert _metric_pass(metric, threshold=0.001, minimum_count=3) is True
