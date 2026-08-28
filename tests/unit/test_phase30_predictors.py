from __future__ import annotations

import math
from datetime import UTC, date, datetime

import pytest

from packages.backtesting.phase30_predictors import (
    PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
    PHASE30_FORBIDDEN_MARKET_FIELDS,
    build_news_shock_records,
    effective_session_index,
    phase30_session_grid,
)
from packages.core.market_calendar import get_market_calendar


def _point_by_date():
    calendar = get_market_calendar("XNYS")
    return {point.session_date: point for point in phase30_session_grid(calendar)}


def test_effective_session_uses_dynamic_normal_close_cutoff() -> None:
    points = _point_by_date()
    ordered = tuple(points.values())
    cutoffs = tuple(point.decision_cutoff_utc for point in ordered)
    target = points[date(2025, 11, 26)]
    index = target.index

    assert effective_session_index(target.decision_cutoff_utc, cutoffs) == index
    assert effective_session_index(
        target.decision_cutoff_utc.replace(microsecond=1), cutoffs
    ) == index + 1


def test_effective_session_handles_shortened_session_and_weekend() -> None:
    points = _point_by_date()
    ordered = tuple(points.values())
    cutoffs = tuple(point.decision_cutoff_utc for point in ordered)

    black_friday = points[date(2025, 11, 28)]
    # XNYS closes 13:00 America/New_York on Black Friday, so the frozen
    # 30-minute decision cutoff is 17:30 UTC in 2025.
    assert black_friday.regular_close_utc == datetime(2025, 11, 28, 18, 0, tzinfo=UTC)
    assert black_friday.decision_cutoff_utc == datetime(2025, 11, 28, 17, 30, tzinfo=UTC)

    assert effective_session_index(
        datetime(2025, 11, 28, 17, 31, tzinfo=UTC), cutoffs
    ) == points[date(2025, 12, 1)].index
    assert effective_session_index(
        datetime(2025, 11, 29, 15, 0, tzinfo=UTC), cutoffs
    ) == points[date(2025, 12, 1)].index


def test_news_surprise_uses_exact_zero_filled_twenty_session_baseline() -> None:
    calendar = get_market_calendar("XNYS")
    sessions = phase30_session_grid(calendar)
    target_index = 25
    target = sessions[target_index]
    ticker = "BrK.B"
    counts = {
        (ticker, target_index): 3,
        (ticker, target_index - 1): 1,
        (ticker, target_index - 5): 2,
    }
    records = build_news_shock_records(
        counts=counts,
        sessions=sessions,
        start_date=target.session_date,
        end_date=target.session_date,
        contract_version=PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
    )
    assert len(records) == 1
    expected_mean = (math.log1p(1) + math.log1p(2)) / 20.0
    assert records[0]["previous_20_log1p_mean"] == pytest.approx(expected_mean)
    assert records[0]["news_surprise"] == pytest.approx(math.log1p(3) - expected_mean)
    assert records[0]["current_unique_article_count"] == 3


def test_provider_native_ticker_case_remains_distinct_and_no_market_fields() -> None:
    calendar = get_market_calendar("XNYS")
    sessions = phase30_session_grid(calendar)
    target_index = 25
    target = sessions[target_index]
    counts = {
        ("BrK.B", target_index): 1,
        ("brk.b", target_index): 2,
    }
    records = build_news_shock_records(
        counts=counts,
        sessions=sessions,
        start_date=target.session_date,
        end_date=target.session_date,
        contract_version=PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
    )
    assert [row["ticker"] for row in records] == ["BrK.B", "brk.b"]
    assert all(
        not any(field in row for field in PHASE30_FORBIDDEN_MARKET_FIELDS)
        for row in records
    )
