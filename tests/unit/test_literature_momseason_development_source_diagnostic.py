from __future__ import annotations

from datetime import date

from packages.backtesting.literature_momseason_development_source_diagnostic import (
    diagnose_cached_source_rows,
)


def test_diagnostic_preserves_shared_source_key_and_counts_frozen_rows() -> None:
    plan_rows = [
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_old_safe",
            "historical_ticker": "SAFE",
        },
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_new_safe",
            "historical_ticker": "SAFE",
        },
        {
            "endpoint_session": "2023-04-28",
            "instrument_id": "ins_other",
            "historical_ticker": "AAA",
        },
    ]
    holdings = [
        {
            "target_month": "2023-04",
            "hypothesis_id": "momseason_short_year1",
            "side": "LONG",
            "instrument_id": "ins_old_safe",
            "prior_endpoint_session": "2023-03-31",
            "target_endpoint_session": "2023-04-28",
        },
        {
            "target_month": "2023-04",
            "hypothesis_id": "momseason_years2_5",
            "side": "SHORT",
            "instrument_id": "ins_new_safe",
            "prior_endpoint_session": "2023-03-31",
            "target_endpoint_session": "2023-04-28",
        },
    ]
    source_results = {
        (date(2023, 3, 31), "SAFE"): {
            "symbol": "SAFE",
            "availability_status": "ZERO_BAR",
            "adjusted_close": None,
        },
        (date(2023, 4, 28), "AAA"): {
            "symbol": "AAA",
            "availability_status": "AVAILABLE",
            "adjusted_close": 10.0,
        },
    }

    result = diagnose_cached_source_rows(
        plan_rows=plan_rows,
        holdings=holdings,
        source_results=source_results,
    )

    assert result["unavailable_plan_rows"] == 2
    assert result["unavailable_source_keys"] == 1
    assert result["unavailable_status_counts"] == {"ZERO_BAR": 2}
    assert result["blocked_holdings"] == 2
    assert result["blocked_holdings_by_hypothesis"] == {
        "momseason_short_year1": 1,
        "momseason_years2_5": 1,
    }
    assert result["details"] == [
        {
            "endpoint_session": "2023-03-31",
            "historical_ticker": "SAFE",
            "availability_status": "ZERO_BAR",
            "instrument_ids": ["ins_new_safe", "ins_old_safe"],
            "instrument_rows": 2,
            "prior_holding_hits": 2,
            "target_holding_hits": 0,
            "blocked_holdings": 2,
            "hypotheses": ["momseason_short_year1", "momseason_years2_5"],
            "target_months": ["2023-04"],
        }
    ]


def test_one_holding_missing_both_endpoints_is_counted_once() -> None:
    plan_rows = [
        {
            "endpoint_session": "2024-01-31",
            "instrument_id": "ins_x",
            "historical_ticker": "XXX",
        },
        {
            "endpoint_session": "2024-02-29",
            "instrument_id": "ins_x",
            "historical_ticker": "XXX",
        },
    ]
    holdings = [
        {
            "target_month": "2024-02",
            "hypothesis_id": "momseason_short_year1",
            "side": "LONG",
            "instrument_id": "ins_x",
            "prior_endpoint_session": "2024-01-31",
            "target_endpoint_session": "2024-02-29",
        }
    ]
    source_results = {
        (date(2024, 1, 31), "XXX"): {
            "symbol": "XXX",
            "availability_status": "ZERO_BAR",
        },
        (date(2024, 2, 29), "XXX"): {
            "symbol": "XXX",
            "availability_status": "ZERO_BAR",
        },
    }

    result = diagnose_cached_source_rows(
        plan_rows=plan_rows,
        holdings=holdings,
        source_results=source_results,
    )

    assert result["unavailable_plan_rows"] == 2
    assert result["unavailable_source_keys"] == 2
    assert result["blocked_holdings"] == 1
    assert result["blocked_holdings_by_hypothesis"] == {"momseason_short_year1": 1}
    assert result["blocked_holdings_by_target_month"] == {"2024-02": 1}
    assert sum(item["prior_holding_hits"] for item in result["details"]) == 1
    assert sum(item["target_holding_hits"] for item in result["details"]) == 1


def test_missing_manifest_source_is_reported_not_silently_dropped() -> None:
    plan_rows = [
        {
            "endpoint_session": "2025-01-31",
            "instrument_id": "ins_missing",
            "historical_ticker": "MISS",
        }
    ]
    holdings = [
        {
            "target_month": "2025-02",
            "hypothesis_id": "momseason_years2_5",
            "side": "SHORT",
            "instrument_id": "ins_missing",
            "prior_endpoint_session": "2025-01-31",
            "target_endpoint_session": "2025-02-28",
        }
    ]

    result = diagnose_cached_source_rows(
        plan_rows=plan_rows,
        holdings=holdings,
        source_results={},
    )

    assert result["unavailable_status_counts"] == {"TARGET_UNIT_NOT_MATERIALIZED": 1}
    assert result["blocked_holdings"] == 1
