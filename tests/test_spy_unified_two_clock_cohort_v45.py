from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pytest

from packages.data import spy_unified_two_clock_cohort_v45 as v45
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


DAY = "2025-06-09"
EXP = "2025-07-18"


def original(day=DAY, *, quality=True):
    return {
        "date_et": day,
        "expiration": EXP,
        "strike": "100",
        "status": v45.ORIGINAL_STATUS if quality else "SOURCE_QUALITY_UNQUALIFIED",
        "reason_codes": [] if quality else ["ORIGINAL_CALL_PUT_OI_UNQUALIFIED"],
        "source_original_spy_spot_0959": "100.2",
        "source_10_01_call": {"status": "QUOTE_MICROSTRUCTURE_PASSES",
                              "timestamp_et": f"{day}T10:01:00-04:00", "bid": 3.2, "ask": 3.25},
        "source_10_01_put": {"status": "QUOTE_MICROSTRUCTURE_PASSES",
                             "timestamp_et": f"{day}T10:01:00-04:00", "bid": 3.3, "ask": 3.35},
        "source_decision_morning_oi": {"status": "OI_SOURCE_FILTER_PASSES",
                                      "source_sha256": "a"*64},
        "call_put_quote_time_skew_seconds": 0.0,
    }


def make_quote_data(row, *, offset=0, missing_put=False):
    sources = {}
    for need in v45.original_predecision_demands([row]):
        if missing_put and need["kwargs"]["right"] == "put":
            continue
        right = need["kwargs"]["right"]
        source_row = {
            "symbol": "SPY", "expiration": row["expiration"],
            "strike": row["strike"], "right": right,
            "timestamp": row["date_et"] + (
                "T09:59:02-04:00" if offset == 2 and right == "put"
                else "T09:59:00-04:00"),
            "bid": 3.0, "ask": 3.1,
            "bid_size": 1, "ask_size": 1,
        }
        sources[need["purpose"]] = (
            need, {"status": "CACHE_HIT", "source_rows": (source_row,),
                   "query_id": "q"+right, "source_sha256": "a"*64},
        )
    return sources


def alternate(day=DAY):
    return {
        "date_et": day,
        "status": v45.ALTERNATE_STATUS,
        "expiration": EXP, "strike": "101",
        "spot_0959": 100.2,
        "call_open_interest": 120,
        "put_open_interest": 160,
        "call_oi_message_et": day + "T06:30:00-04:00",
        "put_oi_message_et": day + "T06:30:00-04:00",
        "source_oi_query_id": "oi", "source_oi_sha256": "e"*64,
        "quote_quality": {
            "pretrade_0959": {
                "call": {"status": "PRETRADE_QUOTE_0959_PASSES",
                         "bid": 3.1, "ask": 3.2},
                "put": {"status": "PRETRADE_QUOTE_0959_PASSES",
                        "bid": 3.3, "ask": 3.4},
                "skew_seconds": 0.0,
            },
            "execution_1001": {
                "call": {"status": "QUOTE_MICROSTRUCTURE_PASSES",
                         "bid": 3.2, "ask": 3.3},
                "put": {"status": "QUOTE_MICROSTRUCTURE_PASSES",
                        "bid": 3.4, "ask": 3.5},
                "skew_seconds": 0.0,
            },
        },
        "reason_codes": [],
        "real_historical_entry_signal": None,
        "historical_profitability": None,
        "broker_fill_asserted": False,
        "independent_oi_publication_confirmed": False,
        "original_expiration": EXP,
        "original_strike": "100",
    }


def test_original_pretrade_demand_is_separate_from_1001_and_unbounded_by_frozen_count():
    rows = [original((date(2025, 1, 1) + timedelta(days=k)).isoformat())
            for k in range(420)]
    rows += [original("2026-03-01", quality=False)]
    demands = list(v45.original_predecision_demands(rows))
    assert len(demands) == 840
    assert set(x["kwargs"]["time_of_day_et"] for x in demands) == {"09:59:00.000"}
    assert set(x["kwargs"]["right"] for x in demands) == {"call", "put"}


def test_0959_exact_quote_and_1001_original_are_reused_with_no_fill_claim():
    row = original()
    c = v45.original_two_clock_result(row, make_quote_data(row))
    assert c["status"] == "TWO_CLOCK_SOURCE_QUALITY_PASSES"
    assert c["quote_quality"]["pretrade_0959"]["call"]["timestamp_et"].endswith("09:59:00-04:00")
    assert c["quote_quality"]["execution_1001"]["call"] is row["source_10_01_call"]
    assert c["historically_executable_fill"] is None
    assert c["historical_pit_american_iv"] is None


def test_original_pair_time_skew_above_one_second_rejected():
    row = original()
    c = v45.original_two_clock_result(row, make_quote_data(row, offset=2))
    assert c["status"] == "TWO_CLOCK_SOURCE_QUALITY_UNQUALIFIED"
    assert "ORIGINAL_PRETRADE_PAIR_SKEW_OVER_1S" in c["reason_codes"]


def test_missing_pretrade_quote_blocks_original_not_backfilled_from_later_quote():
    row = original()
    c = v45.original_two_clock_result(row, make_quote_data(row, missing_put=True))
    assert c["status"] == "TWO_CLOCK_SOURCE_QUALITY_UNQUALIFIED"
    assert "PUT_PRETRADE_0959_SOURCE_MISSING" in c["reason_codes"]


def test_alternate_is_separate_variant_not_frozen_original():
    r = v45.alternate_two_clock_result(original(quality=False), alternate())
    assert r["status"] == "TWO_CLOCK_SOURCE_QUALITY_PASSES"
    assert r["cohort_origin"] == "V44_OI_ALTERNATE_VARIANT"
    assert r["strike"] == "101"
    assert r["historically_executable_fill"] is None


def test_unified_361_date_coverage_and_50_original_abstentions(monkeypatch):
    dates = [(date(2018, 1, 1) + timedelta(days=k)).isoformat() for k in range(361)]
    orig = [original(d, quality=k < 178) for k,d in enumerate(dates)]
    recovered = []
    for k in range(178, 352):
        r = alternate(dates[k])
        if k >= 339:
            r["status"] = "ALTERNATE_SOURCE_QUALITY_UNQUALIFIED"
        recovered.append(r)
    assert len(recovered) == 174
    # Select 161 recoveries; leave 13 incomplete.
    for j, r in enumerate(recovered):
        r["status"] = v45.ALTERNATE_STATUS if j < 161 else "NO_ALTERNATE"
    receipts = {o["date_et"]: make_quote_data(o) for o in orig[:178]}
    acq = {
        "source_uses_requested": 356,
        "persisted_cache_hits": 0,
        "provider_dispatch_attempts": 356,
        "source_uses_failed_or_unresolved": 0,
    }
    output = v45.combined_report(
        {"fingerprint": "v43"}, {"fingerprint": "v44"},
        orig, recovered, receipts, acq,
    )
    assert output["cohort_status_counts"]["TWO_CLOCK_SOURCE_QUALITY_PASSES"] == 339
    assert output["cohort_status_counts"]["SOURCE_QUALITY_NOT_ELIGIBLE"] == 22
    assert output["cohort_origin_counts"]["ORIGINAL_V43"] == 178
    assert output["cohort_origin_counts"]["V44_OI_ALTERNATE_VARIANT"] == 161
    assert output["historical_profitability"] is None
    assert output["american_iv_computed"] is False
    assert output["original_abstentions_unchanged"] == 50
    assert output["fingerprint"] == _fingerprint({
        k:v for k,v in output.items() if k != "fingerprint"
    })


def test_reject_fingerprint_drift_and_original_cohort_drift():
    with pytest.raises(v45.UnifiedCohortError, match="V44_PINNED"):
        v45.verified_v43_v44({}, {"contract": v45.V44_CONTRACT})
    with pytest.raises(v45.UnifiedCohortError, match="NON_QUALITY"):
        v45.original_two_clock_result(original(quality=False), {})
    with pytest.raises(v45.UnifiedCohortError, match="UNQUALIFIED"):
        v45.alternate_two_clock_result(original(quality=False), {
            "status": "ALTERNATE_SOURCE_QUALITY_UNQUALIFIED",
        })


def test_cross_right_equal_bids_and_asks_flagged_as_review_not_alpha(monkeypatch):
    dates = [(date(2018, 1, 1) + timedelta(days=k)).isoformat() for k in range(361)]
    originals = [original(d, quality=k < 178) for k,d in enumerate(dates)]
    rec = []
    for j,k in enumerate(range(178,352)):
        x = alternate(dates[k])
        x["status"] = v45.ALTERNATE_STATUS if j < 161 else "NO_ALTERNATE"
        rec.append(x)
    first = rec[0]
    first["quote_quality"]["execution_1001"]["put"].update(
        bid=first["quote_quality"]["execution_1001"]["call"]["bid"],
        ask=first["quote_quality"]["execution_1001"]["call"]["ask"],
    )
    receipts = {o["date_et"]: make_quote_data(o) for o in originals[:178]}
    acquisition = {"source_uses_requested":356}
    output = v45.combined_report(
        {"fingerprint":"v43"},{"fingerprint":"v44"},
        originals, rec, receipts, acquisition,
    )
    assert len(output["suspicious_equal_call_put_quotes"]) == 1
    assert output["suspicious_equal_call_put_quotes"][0]["clock"] == "execution_1001"
    assert output["historical_source_presence_is_not_independent_publication_proof"] is True
