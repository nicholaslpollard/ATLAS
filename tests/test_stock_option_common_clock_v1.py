from __future__ import annotations

"""Six-year scenario tests: no provider, no fake fills, never survivor-only."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from packages.simulation.stock_option_common_clock_v1 import (
    CommonClockScenarioError, SameClockCase, TimedMark,
    compare_case, compare_cases,
)


def _mark(year, month, day, price, hour=20, kind="NATIVE_RAW_EOD_STOCK_MARK"):
    return TimedMark(
        date(year, month, day), datetime(year, month, day, hour, 0, tzinfo=UTC),
        price, "a" * 64, kind,
    )


def _case(year=2022):
    # 2022-03-01 Tue signal, 03-02 Wed entry and 03-03 Thu exit. For
    # six-year census tests, use safe year dates independent of real calendar.
    return SameClockCase(
        case_id=f"case-{year}", year=year, ticker="TEST",
        original_signal_utc=datetime(year, 3, 1, 14, 35, tzinfo=UTC),
        selected_option_at_utc=datetime(year, 3, 1, 14, 34, tzinfo=UTC),
        news_cutoff_utc=datetime(year, 3, 1, 14, 35, tzinfo=UTC),
        prior_24h_article_count=2, prior_7d_article_count=5,
        option_symbol=f"TEST{str(year)[2:]}0318C00100000",
        option_expiration=date(year, 3, 18), option_right="call",
        option_multiplier=100, standard_deliverable_verified=True,
        stock_raw_price_basis_verified=True,
        stock_entry=_mark(year, 3, 2, 100),
        stock_exit=_mark(year, 3, 3, 105),
        option_entry_ask=_mark(year, 3, 2, 2.00, kind="HISTORICAL_OPTION_EOD_ASK"),
        option_exit_bid=_mark(year, 3, 3, 2.60, kind="HISTORICAL_OPTION_EOD_BID"),
        option_reference_status="ENTRY_AND_NEXT_REFERENCE_AVAILABLE",
        source_lineage_fingerprint="b" * 64,
    )


def test_both_instruments_use_same_sessions_budget_and_ask_bid():
    result = compare_case(_case(), stock_slippage_bps=0,
                          option_round_trip_fee_per_contract=0)
    assert result["paired_observation_coverage"] is True
    assert result["stock_shares"] == 100
    assert result["stock_reference_pnl"] == pytest.approx(500)
    assert result["option_contracts"] == 50
    assert result["option_reference_pnl"] == pytest.approx(3000)
    assert result["stock_reference_return_fraction"] == pytest.approx(0.05)
    assert result["option_reference_return_fraction"] == pytest.approx(0.30)
    assert result["provider_requests"] == result["actual_fills"] == 0
    assert result["model_reference_pnl_not_backtest_or_paper_pnl"]
    assert result["account_level_portfolio_return"] is None


def test_six_years_keep_unavailable_cases_in_denominator():
    cases = [_case(year) for year in range(2021, 2027)]
    missing = cases[0]
    cases[0] = replace(
        missing, option_entry_ask=None, option_exit_bid=None,
        option_reference_status="NOT_ACQUIRED",
    )
    report = compare_cases(cases)
    assert report["full_signal_denominator"] == 6
    assert report["paired_reference_count"] == 5
    assert report["by_calendar_year"]["2021"]["full_signal_denominator"] == 1
    assert report["by_calendar_year"]["2021"]["paired_eod_reference_count"] == 0
    assert report["by_calendar_year"]["2026"]["paired_eod_reference_count"] == 1
    assert report["portfolio_return"] is None
    assert report["provider_requests"] == 0


def test_mismatched_observation_days_are_not_traded():
    c = _case()
    alternate = _mark(2022, 3, 4, 2.6, kind="HISTORICAL_OPTION_EOD_BID")
    result = compare_case(replace(c, option_exit_bid=alternate))
    assert result["option_status"] == "UNMATCHED_EOD_OBSERVATION_CLOCK"
    assert result["option_reference_pnl"] is None
    assert result["stock_reference_pnl"] is not None


def test_future_contract_selection_and_decision_day_eod_refused():
    c = _case()
    with pytest.raises(CommonClockScenarioError, match="decision drifted"):
        compare_case(replace(
            c, selected_option_at_utc=datetime(2022, 3, 1, 15, tzinfo=UTC)
        ))
    with pytest.raises(CommonClockScenarioError, match="strictly later"):
        compare_case(replace(
            c, stock_entry=_mark(2022, 3, 1, 100)
        ))
    with pytest.raises(CommonClockScenarioError, match="intraday"):
        compare_case(c, mode="ORIGINAL_0935_EXECUTABLE")


def test_adjusted_contract_does_not_create_cash_pnl():
    c = _case()
    result = compare_case(replace(c, standard_deliverable_verified=False))
    assert result["option_status"] == "UNVERIFIED_CONTRACT_DELIVERABLE"
    assert result["option_reference_pnl"] is None
    assert result["stock_status"] == "ILLUSTRATIVE_STOCK_EOD_REFERENCE"


def test_missing_source_and_duplicate_cases_are_not_silently_dropped():
    c = _case()
    with pytest.raises(CommonClockScenarioError, match="required actual mark"):
        compare_case(replace(c, option_exit_bid=None))
    with pytest.raises(CommonClockScenarioError, match="unique original"):
        compare_cases([c, c])
