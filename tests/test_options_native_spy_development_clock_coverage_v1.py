from __future__ import annotations

from datetime import UTC, datetime, timedelta
from copy import deepcopy

import pytest

from packages.core.market_calendar import get_market_calendar
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data import options_native_spy_development_clock_coverage_v1 as mod
from test_options_native_pilot_input_packet_v1 import native
from test_options_native_stock_input_review_v1 import source


def test_full_registered_2018_2025_pilot_demands_are_globally_deduplicated():
    demand, by_month = mod.frozen_clock_demand()
    assert demand["plan_fingerprint"]
    assert len(demand["cases"]) == 411
    assert 1 < len(by_month) <= 125
    assert 1800 < demand["unique_clocks"] < 4000
    assert demand["months"] == sorted(demand["months"])
    assert all(case["decision_date"] < "2026-01-01" for case in demand["cases"])
    assert not any(year >= 2026 for year, month in by_month)
    assert len({case["decision_date"] for case in demand["cases"]}) == 411
    assert all(len(case["prior"]) == 21 and len({p["clock"] for p in case["prior"]}) == 21
               for case in demand["cases"])
    assert all(case["decision_utc"] > case["prior"][-1]["clock"] for case in demand["cases"])
    assert all(case["order_eligible_utc"] > case["decision_utc"] for case in demand["cases"])
    assert all(case["spot"] in by_month[(
        int(case["decision_date"][:4]), int(case["decision_date"][5:7])
    )] for case in demand["cases"])


def test_december_2019_january_2020_fixture_clock_reproduces_frozen_calendar():
    demand, month = mod.frozen_clock_demand()
    pilot = next(c for c in demand["cases"] if c["decision_date"] == "2020-01-06")
    assert pilot["spot"] == "2020-01-06T14:59:00+00:00"
    assert pilot["prior"][0]["session"] == "2019-12-04"
    assert pilot["prior"][-1]["session"] == "2020-01-03"
    early = next(row for row in pilot["prior"] if row["session"] == "2019-12-24")
    assert early["clock"] == "2019-12-24T17:59:00+00:00"
    assert early["clock"] in month[(2019, 12)]


def test_frozen_selected_native_months_are_not_reselected_from_other_files(source):
    ctx = source
    layout = ctx["layout"]
    packet = __import__("json").loads(ctx["packet_path"].read_text())
    expected = {(2019, 12), (2020, 1)}
    records = mod.select_native_units(layout, packet, expected)
    assert set(records) == expected
    assert all("SPY" in r["symbols"] and r["provider_timeframe"] == "1Min" for r in records.values())


def test_missing_month_is_explicit_not_filled_from_another_unit(source):
    ctx = source
    packet = __import__("json").loads(ctx["packet_path"].read_text())
    records = mod.select_native_units(ctx["layout"], packet, {(2019, 12), (2017, 1)})
    assert (2019, 12) in records
    assert (2017, 1) not in records


def test_projection_preserves_every_gap_and_never_promotes_raw_completeness():
    demand = {
        "cases": [
            {"decision_date": "2020-01-06", "decision_utc": "2020-01-06T15:00:00+00:00",
             "quote_query_fingerprint": "a" * 64,
             "prior": [{"clock": "2019-12-04T20:59:00+00:00"}],
             "spot": "2020-01-06T14:59:00+00:00"},
            {"decision_date": "2020-01-13", "decision_utc": "2020-01-13T15:00:00+00:00",
             "quote_query_fingerprint": "b" * 64,
             "prior": [{"clock": "2020-01-09T20:59:00+00:00"}],
             "spot": "2020-01-13T14:59:00+00:00"},
        ]
    }
    found = {
        "2019-12-04T20:59:00+00:00": {"raw_close": "320.01"},
        "2020-01-06T14:59:00+00:00": {"raw_close": "321.60"},
        "2020-01-13T14:59:00+00:00": {"raw_close": "327.23"},
    }
    # This helper expects the actual fixed 21 prior clocks per case; model
    # them explicitly so the presence count can never be inflated.
    for case in demand["cases"]:
        first = case["prior"][0]["clock"]
        case["prior"] = [{"clock": first if i == 0 else f"missing-{i}-{case['decision_date']}"}
                         for i in range(21)]
    for c in demand["cases"][0]["prior"][1:]:
        found[c["clock"]] = {"raw_close": "320"}
    output = mod.project_case_coverage(demand, found)
    assert output["raw_complete"] == 1
    assert output["raw_with_gaps"] == 1
    assert output["cases"][0]["exact_minutes_present"] == 22
    assert output["cases"][0]["historical_input_accepted"] is False
    assert output["cases"][0]["forecast_total_variance"] is None
    assert output["cases"][1]["exact_minutes_present"] == 1
    assert len(output["cases"][1]["missing_clocks"]) == 21


def test_physical_minute_provenance_and_duplicate_fail_closed():
    stamp = datetime(2020, 1, 6, 14, 59, tzinfo=UTC)
    uid = "a" * 64
    good = ("SPY", stamp, stamp.date(), "regular", 321.60,
            "1m", "stock_minute_aggregates", "alpaca",
            "alpaca:sip:1Min:raw:asof=-:v2:unit=" + uid, False)
    assert mod.verify_physical_rows([good], {stamp}, uid) == {
        stamp.isoformat(): "321.6"
    }
    with pytest.raises(mod.PilotClockCoverageError, match="duplicates"):
        mod.verify_physical_rows([good, good], {stamp}, uid)
    for index, bad in ((3, "extended"), (7, "another-provider"), (8, "wrong-source"),
                       (9, True)):
        corrupted = list(good)
        corrupted[index] = bad
        with pytest.raises(mod.PilotClockCoverageError, match="provenance"):
            mod.verify_physical_rows([tuple(corrupted)], {stamp}, uid)
    with pytest.raises(mod.PilotClockCoverageError, match="duplicates"):
        mod.verify_physical_rows([good], {stamp + timedelta(minutes=1)}, uid)


def test_spy_decision_clock_bounds_and_protected_year_exclusion():
    demand, by_month = mod.frozen_clock_demand()
    start = min(month for month in by_month)
    end = max(month for month in by_month)
    assert start[0] == 2017
    assert end[0] == 2025
    assert len(demand["cases"]) == 411


def test_bounded_monthly_reader_reproduces_retained_2020_spy_calibration(source, monkeypatch):
    """All source IO occurs against invented accepted native parquet/checkpoints."""
    from packages.data import options_native_stock_input_review_v1 as old_review
    ctx = source
    prior = old_review.review_options_native_stock_inputs(ctx["settings"], binding=ctx["binding"])
    monkeypatch.setattr(mod, "_read_report", lambda *_args, **_kwargs: prior)
    monkeypatch.setattr(mod, "DEFAULT_BINDING", ctx["binding"])
    requested = prior["observations"]
    months = {}
    for row in requested:
        stamp = datetime.fromisoformat(row["interval_start_utc"])
        month = (stamp.year, stamp.month)
        months.setdefault(month, {})[row["interval_start_utc"]] = stamp
    old = [{
        "session": row["session_date"], "clock": row["interval_start_utc"]
    } for row in requested if row["role"] == "PRIOR_REGULAR_CLOSE"]
    case = {
        "decision_date": "2020-01-06", "decision_utc": "2020-01-06T15:00:00+00:00",
        "order_eligible_utc": "2020-01-06T15:01:00+00:00",
        "quote_query_fingerprint": "a" * 64,
        "prior": old, "spot": requested[-1]["interval_start_utc"],
    }
    demand = {"plan_fingerprint": "b" * 64,
              "cases": [dict(case) for _ in range(411)],
              "unique_clocks": 22}
    monkeypatch.setattr(mod, "frozen_clock_demand", lambda: (demand, months))
    report = mod.review_spy_development_minute_coverage(ctx["settings"])
    assert report["target_weekly_cases"] == 411
    assert report["raw_complete_weekly_cases"] == 411
    assert report["raw_incomplete_weekly_cases"] == 0
    assert report["observed_exact_clocks"] == 22
    assert report["target_months"] == report["scanned_monthly_units"] == 2
    assert report["observations"][case["spot"]]["raw_close"] == prior["observations"][-1]["raw_close"]
    assert report["scan_scope"]["daily_units"] == report["scan_scope"]["options"] == 0
    assert report["pilot_input_acceptance"] is False
    assert report["forecast_total_variance"] is None
    assert report["historical_publication_and_adjustment_qualified"] is False
