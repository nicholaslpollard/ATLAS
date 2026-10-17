from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.data import options_native_spy_publication_evidence_demand_v1 as mod
from packages.data.options_native_spy_full_period_retrospective_dividend_variance_v1 import (
    reference_schedule,
)
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT


def synthetic_reports():
    schedule = reference_schedule()
    events = [
        {"ex_date": ex, "cash_per_share_usd": "1.096775" if ex == "2018-03-16" else str(amt),
         "source_row": 9200 - index}
        for index, (ex, amt) in enumerate(schedule.items())
    ]
    issuer = {
        "contract": mod.ISSUER_CONTRACT,
        "status": "FULL_33_SPY_ISSUER_CASH_EVENTS_RECONCILED_RETROSPECTIVE_NO_PIT",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "issuer_event_count": 33,
        "archived_cash_events_matched_by_ex_date": 32,
        "missing_from_original_action_archive": ["2018-06-15"],
        "issuer_publication_clock_in_2018_2025_proved": False,
        "issuer_asof_amendment_or_revision_history_proved": False,
        "other_corporate_action_coverage_qualified": False,
        "historical_backtest_authorized": False,
        "pilot_input_acceptance": False,
        "authority": dict(AUTHORITY),
        "issuer_period_events": events,
    }
    coverage = {
        "contract": "atlas-options-native-spy-development-minute-clock-coverage-v1",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "target_weekly_cases": 411,
        "raw_complete_weekly_cases": 407,
        "raw_incomplete_weekly_cases": 4,
        "observed_exact_clocks": 2406,
        "pilot_input_acceptance": False,
        "authority": dict(AUTHORITY),
        "cases": [],
    }
    grid = {
        "contract": "atlas-options-native-spy-retrospective-dividend-variance-grid-v1",
        "status": "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "fixed_weekly_decision_count": 411,
        "physically_price_complete_decisions": 407,
        "retrospective_dividend_touched_decisions": 149,
        "pilot_input_acceptance": False,
        "authority": dict(AUTHORITY),
        "weekly_retrospective_sensitivity": [],
    }
    # Every fake interval ends BEFORE the 2018-06-18 decision; only first
    # 149 price-complete cases overlap June 2018 cash on a return-ending date.
    baseline = datetime(2018, 6, 1, 20, 59, tzinfo=UTC)
    earlier = datetime(2018, 5, 1, 20, 59, tzinfo=UTC)
    for index in range(411):
        touched = index < 149
        start = baseline if touched else earlier
        keys = [(start + timedelta(days=i)).isoformat() for i in range(21)]
        ex = "2018-06-15"
        missing = ["2019-08-12T19:59:00+00:00"] if index >= 407 else []
        coverage["cases"].append({
            "decision_date": "2018-06-18",
            "decision_utc": "2018-06-18T14:00:00+00:00",
            "prior_close_keys": keys,
            "missing_clocks": missing,
            "historical_input_accepted": False,
            "forecast_total_variance": None,
        })
        grid["weekly_retrospective_sensitivity"].append(
            {"decision_date": "2018-06-18",
             "status": "RAW_PRICE_GAP_NO_VARIANCE_DIAGNOSTIC"}
            if missing else
            {"decision_date": "2018-06-18",
             "status": "RETROSPECTIVE_VARIANCE_SENSITIVITY_ONLY",
             "retrospective_dividends_in_return_end_dates":
                [{"ex_date": ex, "retrospective_cash_usd": "1.245568"}] if touched else []}
        )
    return issuer, coverage, grid


def test_full_offline_evidence_queue_retains_no_pit_promotion():
    issuer, coverage, grid = synthetic_reports()
    result = mod.crosscheck_and_build_event_demand(issuer, coverage, grid)
    assert result["event_count"] == 33
    assert len(result["events"]) == 33
    assert len(result["decision_exposures"]) == 411
    assert result["price_complete_cases"] == 407
    assert result["price_complete_cases_exposed_to_dividends"] == 149
    assert len(result["price_incomplete_cases"]) == 4
    assert result["events_with_original_pit_source_receipt"] == 0
    assert result["events_with_research_publication_lead"] == 3
    june = next(row for row in result["events"] if row["ex_date"] == "2018-06-15")
    assert june["frozen_weekly_lookbacks_using_event"] == 149
    assert june["physically_price_complete_weekly_lookbacks"] == 149
    assert june["lead_displayed_earlier_than_first_relevant_decision"] is True
    assert june["historical_original_page_hashed_and_retained"] is False
    assert june["economic_return_feature_accepted"] is False
    assert len(result["events_with_no_registered_lookback_usage"]) == 32


def test_source_leads_retain_timezones_but_are_not_proof():
    for lead in mod.PUBLICATION_LEADS:
        timestamp = mod._utc(lead["displayed_publication_local"])
        assert timestamp.tzinfo is UTC
        assert timestamp.year == int(lead["ex_date"][:4])
    with pytest.raises(mod.SpyPublicationDemandError):
        mod._utc("2018-06-14T19:34:00")
    with pytest.raises(mod.SpyPublicationDemandError):
        mod._utc("unknown")


@pytest.mark.parametrize("mutator", [
    lambda issuer, coverage, grid: issuer.update(pilot_input_acceptance=True),
    lambda issuer, coverage, grid: issuer.update(issuer_event_count=32),
    lambda issuer, coverage, grid: issuer["issuer_period_events"].pop(),
    lambda issuer, coverage, grid: issuer["issuer_period_events"][0].update(ex_date="2018-06-15"),
    lambda issuer, coverage, grid: coverage.update(raw_complete_weekly_cases=411),
    lambda issuer, coverage, grid: coverage["cases"][0].update(forecast_total_variance="1"),
    lambda issuer, coverage, grid: coverage["cases"][0].update(decision_utc="2018-05-01T14:00:00+00:00"),
    lambda issuer, coverage, grid: grid.update(retrospective_dividend_touched_decisions=148),
    lambda issuer, coverage, grid: grid["weekly_retrospective_sensitivity"][0].update(retrospective_dividends_in_return_end_dates=[]),
])
def test_missing_source_coverage_or_authority_drift_blocks(mutator):
    issuer, coverage, grid = synthetic_reports()
    mutator(issuer, coverage, grid)
    with pytest.raises((mod.SpyPublicationDemandError, KeyError, ValueError)):
        mod.crosscheck_and_build_event_demand(issuer, coverage, grid)
