from __future__ import annotations

from packages.backtesting.literature_momseason_total_return_source_v3 import (
    MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR,
    MOMSEASON_SAME_CURRENCY_VALUE_MAX_RELATIVE_ERROR,
    MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR,
    MOMSEASON_US_EQUITY_BAR_CURRENCY,
    _currency,
    _currency_relation,
    _metric,
)


def test_currency_normalization_is_explicit_and_case_insensitive() -> None:
    assert _currency(" usd ") == "USD"
    assert _currency("cad") == "CAD"
    assert _currency("") is None
    assert _currency(None) is None


def test_cross_currency_dividend_is_not_directly_comparable() -> None:
    assert _currency_relation("CAD", "USD") == "CROSS_CURRENCY"
    assert _currency_relation("USD", "USD") == "SAME_CURRENCY"
    assert _currency_relation(None, "USD") == "MISSING_CURRENCY_METADATA"


def test_source_semantics_tolerances_are_tight_and_frozen_pre_outcome() -> None:
    assert MOMSEASON_US_EQUITY_BAR_CURRENCY == "USD"
    assert MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR == 0.001
    assert MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR == 0.001
    assert MOMSEASON_SAME_CURRENCY_VALUE_MAX_RELATIVE_ERROR == 0.001


def test_metric_ignores_missing_values_and_reports_worst_case() -> None:
    result = _metric([None, 0.0, 0.0002, 0.0004])
    assert result["count"] == 3
    assert result["min"] == 0.0
    assert result["median"] == 0.0002
    assert result["max"] == 0.0004
