from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.data import options_native_spy_full_period_retrospective_dividend_variance_v1 as mod
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY


def archived_candidates():
    schedule = mod.reference_schedule()
    candidates = [
        {"action_type": "cash_dividends",
         "historical_available_at_utc": None,
         "point_in_time_qualified": False,
         "payload": {"symbol": "SPY", "ex_date": d,
                     "rate": str(v - Decimal("0.000005") if d == "2018-03-16"
                                 else v - Decimal("0.0000001") if d == "2020-06-19"
                                 else v)}}
        for d, v in schedule.items() if d != mod.KNOWN_ABSENCE
    ]
    return {"action_candidates": candidates,
            "action_candidates_by_type": {"cash_dividends": 32},
            "archival_candidates_with_unknown_effective_date": 0}


def test_33_retrospective_us_ex_dates_reconcile_all_32_archive_dates():
    schedule = mod.reference_schedule()
    assert len(schedule) == 33
    assert schedule[mod.KNOWN_ABSENCE] == Decimal("1.245568")
    summary = mod.reconcile_reference_to_archive(archived_candidates(), schedule)
    assert summary["reference_event_count"] == 33
    assert summary["archived_event_count"] == 32
    assert summary["exact_ex_date_matches"] == 32
    assert summary["known_missing_ex_dates"] == ["2018-06-15"]
    assert summary["retrospective_nondividend_events_proved_absent"] is False
    assert [r["ex_date"] for r in summary["rounded_rate_residuals"]] == [
        "2018-03-16", "2020-06-19",
    ]
    assert all(abs(Decimal(r["archived_minus_reference"])) <= mod.RATE_TOLERANCE
               for r in summary["rounded_rate_residuals"])


@pytest.mark.parametrize("change", ["restore_missing", "additional_ex_date", "oversized_cash",
                                    "ex_date_changed", "pit_claim", "noncash", "missing_rate"])
def test_drift_in_archive_or_amount_blocks_hypothetical_source_consistency(change):
    archive = archived_candidates()
    if change == "restore_missing":
        archive["action_candidates"].append({
            "action_type": "cash_dividends", "point_in_time_qualified": False,
            "historical_available_at_utc": None,
            "payload": {"symbol": "SPY", "ex_date": "2018-06-15", "rate": "1.245568"},
        })
    if change == "additional_ex_date":
        archive["action_candidates"][0]["payload"]["ex_date"] = "2017-12-16"
    if change == "oversized_cash":
        archive["action_candidates"][0]["payload"]["rate"] = "1.90"
    if change == "ex_date_changed":
        archive["action_candidates"][0]["payload"]["ex_date"] = "2018-06-15"
    if change == "pit_claim":
        archive["action_candidates"][0]["point_in_time_qualified"] = True
    if change == "noncash":
        archive["action_candidates"][0]["action_type"] = "splits"
    if change == "missing_rate":
        archive["action_candidates"][0]["payload"].pop("rate")
    with pytest.raises((mod.RetrospectiveDividendGridError, ValueError)):
        mod.reconcile_reference_to_archive(archive, mod.reference_schedule())


def fixture_21_closes():
    # 2018-06-15 is a return-ending date, not a baseline. These are invented
    # values, not claims about 2018 historical market observations.
    start = datetime(2018, 6, 1, 19, 59, tzinfo=UTC)
    timestamps = [start + timedelta(days=i) for i in range(21)]
    keys = [t.isoformat() for t in timestamps]
    closes = {
        key: {"raw_close": str(Decimal("270") + Decimal(i)),
              "status": "RAW_MINUTE_PRESENT", "historical_available_at_utc": None}
        for i, key in enumerate(keys)
    }
    return keys, closes


def test_dividend_is_included_only_on_return_end_date_and_is_not_tradable():
    keys, closes = fixture_21_closes()
    sample = mod.case_volatility(keys, closes, mod.reference_schedule())
    assert [x["ex_date"] for x in sample["retrospective_dividends_in_return_end_dates"]] == [
        "2018-06-15",
    ]
    assert sample["historical_feature_accepted"] is False
    assert Decimal(sample["annualized_raw_price_volatility"]) > 0
    assert Decimal(sample["annualized_retrospective_dividend_conditioned_volatility"]) > 0
    assert sample["archived_dividend_adjustment_would_be_lookahead_without_pit_proof"] is True
    assert sample["elapsed_calendar_seconds"] == 20 * 86400


def test_first_close_is_only_baseline_no_distribution_applied():
    keys, closes = fixture_21_closes()
    schedule = {"2018-06-01": Decimal("1.24")}
    sample = mod.case_volatility(keys, closes, schedule)
    assert sample["retrospective_dividends_in_return_end_dates"] == []
    assert sample["annualized_raw_price_volatility"] == sample[
        "annualized_retrospective_dividend_conditioned_volatility"
    ]


@pytest.mark.parametrize("mutation", ["missing_bar", "late_pit", "duplicate", "reverse", "zero_price",
                                      "nan", "naive"])
def test_source_clock_and_price_fail_closed(mutation):
    keys, closes = fixture_21_closes()
    if mutation == "missing_bar":
        del closes[keys[3]]
    elif mutation == "late_pit":
        closes[keys[3]]["historical_available_at_utc"] = "2018-06-04T00:00:00+00:00"
    elif mutation == "duplicate":
        keys[4] = keys[3]
    elif mutation == "reverse":
        keys[3], keys[4] = keys[4], keys[3]
    elif mutation == "zero_price":
        closes[keys[4]]["raw_close"] = "0"
    elif mutation == "nan":
        closes[keys[4]]["raw_close"] = "NaN"
    elif mutation == "naive":
        keys[4] = keys[4].replace("+00:00", "")
    with pytest.raises((mod.RetrospectiveDividendGridError, ValueError)):
        mod.case_volatility(keys, closes, mod.reference_schedule())


def test_json_only_integration_requires_all_four_pinned_reports(tmp_path, monkeypatch):
    import types
    settings = types.SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    with pytest.raises(Exception):
        mod.build_full_period_retrospective_grid(settings)
