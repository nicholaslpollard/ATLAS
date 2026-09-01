from __future__ import annotations

from datetime import date

from packages.backtesting.literature_momseason_policy import (
    LITERATURE_MOMSEASON_FORMATION_START,
)
from packages.backtesting.literature_momseason_total_return_source import (
    MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END,
)
from packages.backtesting.literature_momseason_total_return_source_v2 import (
    _best_overlap_match,
    _massive_case_key,
    build_alpaca_action_index,
    expected_scale_change_from_alpaca,
    expected_scale_change_from_massive,
)


def test_v2_bar_barrier_remains_before_first_target_month() -> None:
    assert MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END == date(2021, 8, 31)
    assert MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END < LITERATURE_MOMSEASON_FORMATION_START


def test_action_index_separates_dividends_splits_and_non_action_rows() -> None:
    rows = [
        {
            "_alpaca_action_type": "cash_dividend",
            "id": "d1",
            "symbol": "AAA",
            "ex_date": "2020-04-15",
            "rate": "0.25",
        },
        {
            "_alpaca_action_type": "forward_split",
            "id": "s1",
            "symbol": "BBB",
            "ex_date": "2020-08-31",
            "old_rate": "1",
            "new_rate": "4",
        },
        {
            "_alpaca_action_type": "name_change",
            "id": "n1",
            "symbol": "CCC",
            "ex_date": "2020-01-01",
        },
    ]
    index = build_alpaca_action_index(rows)
    assert list(index) == [
        ("dividend", "AAA", "2020-04-15"),
        ("split", "BBB", "2020-08-31"),
    ]


def test_massive_case_key_maps_factor_variants_to_same_dividend_family() -> None:
    missing = {
        "kind": "dividend_missing_factor",
        "ticker": "AAA",
        "event_date": "2020-04-15",
    }
    factor = {
        "kind": "dividend_with_factor",
        "ticker": "AAA",
        "event_date": "2020-04-15",
    }
    assert _massive_case_key(missing) == _massive_case_key(factor) == (
        "dividend",
        "AAA",
        "2020-04-15",
    )


def test_overlap_match_compares_alpaca_rate_to_massive_original_cash_amount() -> None:
    case = {
        "kind": "dividend_missing_factor",
        "ticker": "AAA",
        "event_date": "2020-04-15",
        "massive_cash_amount": 0.25,
        "massive_split_adjusted_cash_amount": 0.05,
        "massive_historical_adjustment_factor": None,
    }
    candidates = [
        {
            "_alpaca_action_type": "cash_dividend",
            "id": "d1",
            "symbol": "AAA",
            "ex_date": "2020-04-15",
            "rate": "0.25",
        }
    ]
    result = _best_overlap_match(case, candidates)
    assert result["alpaca_action_match"] is True
    assert result["massive_comparison_value"] == 0.25
    assert result["alpaca_value"] == 0.25
    assert result["value_relative_error"] == 0.0


def test_missing_massive_factor_does_not_prevent_independent_scale_reconstruction() -> None:
    case = {
        "kind": "dividend_missing_factor",
        "massive_cash_amount": 0.50,
        "massive_historical_adjustment_factor": None,
        "alpaca_value": 0.50,
    }
    expected = 100.0 / 99.5
    assert expected_scale_change_from_massive(case, 100.0) == expected
    assert expected_scale_change_from_alpaca(case, 100.0) == expected


def test_massive_and_alpaca_scale_expectations_remain_independent() -> None:
    case = {
        "kind": "dividend_missing_factor",
        "massive_cash_amount": 0.50,
        "alpaca_value": 0.40,
    }
    massive = expected_scale_change_from_massive(case, 100.0)
    alpaca = expected_scale_change_from_alpaca(case, 100.0)
    assert massive == 100.0 / 99.5
    assert alpaca == 100.0 / 99.6
    assert massive != alpaca


def test_split_scale_expectations_use_each_provider_ratio_independently() -> None:
    case = {
        "kind": "split",
        "massive_split_ratio": 4.0,
        "alpaca_value": 3.0,
    }
    assert expected_scale_change_from_massive(case, 100.0) == 4.0
    assert expected_scale_change_from_alpaca(case, 100.0) == 3.0
