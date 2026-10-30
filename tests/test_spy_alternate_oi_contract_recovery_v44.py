from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pytest

from packages.data import spy_alternate_oi_contract_recovery_v44 as v44
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


DAY = "2025-06-09"
EXP = "2025-07-18"


def original(day=DAY):
    return {
        "date_et": day,
        "expiration": EXP,
        "strike": "100",
        "source_original_spy_spot_0959": "100.1",
        "reason_codes": ["ORIGINAL_CALL_PUT_OI_UNQUALIFIED"],
    }


def oi_row(right, strike, *, expiration=EXP, oi=200,
           timestamp="2025-06-09T06:30:00-04:00"):
    return {
        "symbol": "SPY", "expiration": expiration,
        "strike": str(strike), "right": right,
        "open_interest": oi, "timestamp": timestamp,
    }


def oi_source(rows):
    return {
        "status": "CACHE_HIT", "source_rows": tuple(rows),
        "query_id": "oi_query", "source_sha256": "a" * 64,
    }


def good_oi():
    return [
        oi_row("call", "100", oi=50), oi_row("put", "100", oi=50),
        oi_row("call", "101", oi=300), oi_row("put", "101", oi=180),
        oi_row("call", "99", oi=100), oi_row("put", "99", oi=100),
        oi_row("call", "100.5", oi=10), oi_row("put", "100.5", oi=1000),
    ]


def quote_row(right, strike, stamp):
    return {
        "symbol": "SPY", "expiration": EXP, "strike": strike,
        "right": right, "bid": 1.75, "ask": 1.80,
        "bid_size": 50, "ask_size": 50, "timestamp": stamp,
    }


def make_quote_sources(chosen, *, late_pretrade=False):
    output = {}
    for item in v44.quote_demands(chosen):
        name = item["purpose"]
        is_pre = "pretrade_0959" in name
        timestamp = (
            "2025-06-09T09:59:02-04:00" if late_pretrade else
            "2025-06-09T09:58:59-04:00"
        ) if is_pre else "2025-06-09T10:01:00-04:00"
        source = {
            "status": "FETCHED_AND_ARCHIVED", "query_id": name,
            "source_sha256": "b"*64,
            "source_rows": (quote_row(item["kwargs"]["right"], chosen["strike"], timestamp),)
        }
        output[name] = (item, source)
    return output


def test_alternative_picks_oi_qualified_nearest_original_expiration():
    selected = v44.discover_alternate(original(), oi_source(good_oi()))
    assert selected["status"] == "ALTERNATE_FROM_PRIOR_STATE_OI"
    assert selected["expiration"] == EXP and selected["strike"] == "101"
    assert selected["call_open_interest"] == 300
    assert selected["put_open_interest"] == 180
    assert selected["spot_0959"] == 100.1
    assert selected["historical_signal"] is None


def test_same_expiration_preferred_only_on_proximity_tie():
    rows = [
        oi_row("call", "104"), oi_row("put", "104"),
        oi_row("call", "100.5", expiration="2025-07-11"),
        oi_row("put", "100.5", expiration="2025-07-11"),
    ]
    selected = v44.discover_alternate(original(), oi_source(rows))
    assert selected["expiration"] == "2025-07-11"
    assert selected["strike"] == "100.5"


def test_no_selection_uses_later_oi_and_no_future_quote_inputs():
    rows = [
        oi_row("call", "101", timestamp="2025-06-09T10:03:00-04:00"),
        oi_row("put", "101"),
    ]
    selected = v44.discover_alternate(original(), oi_source(rows))
    assert selected["status"] == "NO_ALTERNATE"
    assert selected["historical_signal"] is None


def test_pretrade_and_order_quotes_are_distinct_dynamic_demands():
    c = v44.discover_alternate(original(), oi_source(good_oi()))
    needs = list(v44.quote_demands(c))
    assert len(needs) == 4
    assert {x["purpose"] for x in needs} == {
        "call_pretrade_0959_quote", "put_pretrade_0959_quote",
        "call_execution_1001_quote", "put_execution_1001_quote",
    }
    assert {x["kwargs"]["time_of_day_et"] for x in needs} == {
        "09:59:00.000", "10:01:00.000",
    }
    assert all(x["kwargs"]["strike"] == "101" for x in needs)
    assert all(x["kwargs"]["expiration"] == EXP for x in needs)


def test_historical_0959_quote_inputs_and_1001_order_sources_not_promoted():
    c = v44.discover_alternate(original(), oi_source(good_oi()))
    qualified = v44.assess_alternate_quotes(c, make_quote_sources(c))
    assert qualified["status"] == "ALTERNATE_SOURCE_QUALITY_PASSES"
    assert qualified["quote_quality"]["pretrade_0959"]["call"]["status"] == "PRETRADE_QUOTE_0959_PASSES"
    assert qualified["quote_quality"]["execution_1001"]["put"]["status"] == "QUOTE_MICROSTRUCTURE_PASSES"
    assert qualified["real_historical_entry_signal"] is None
    assert qualified["broker_fill_asserted"] is False
    assert qualified["historical_profitability"] is None
    rejected = v44.assess_alternate_quotes(c, make_quote_sources(c, late_pretrade=True))
    assert rejected["status"] == "ALTERNATE_SOURCE_QUALITY_UNQUALIFIED"
    assert "UNQUALIFIED_CALL_PRETRADE_0959_QUOTE" in rejected["reason_codes"]


def test_no_extra_requests_when_original_morning_oi_has_no_candidate():
    empty = v44.discover_alternate(original(), oi_source([
        oi_row("call", "101", oi=1), oi_row("put", "101", oi=3),
    ]))
    assert empty["status"] == "NO_ALTERNATE"
    assert list(v44.quote_demands(empty)) == []


def test_generated_candidate_count_not_capped_by_frozen_361():
    base = v44.discover_alternate(original(), oi_source(good_oi()))
    many = [{**base, "date_et": (date(2018, 1, 1) + timedelta(days=k)).isoformat()}
            for k in range(485)]
    assert sum(len(list(v44.quote_demands(c))) for c in many) == 1940


def test_pinned_v43_report_required():
    with pytest.raises(v44.AlternateSourceError, match="FINGERPRINT"):
        v44.verified_original_cases({
            "contract": v44.V43_CONTRACT,
            "fingerprint": "arbitrary",
            "original_cases": [],
        })


def test_v44_report_preserves_no_signal_and_original_cohort(monkeypatch):
    cases = [
        {"date_et": "2025-06-09", "reason_codes": ["ORIGINAL_CALL_PUT_OI_UNQUALIFIED"]},
        {"date_et": "2025-06-16", "reason_codes": [], "status": "SOURCE_MICROSTRUCTURE_OI_CHECKS_PASS"},
    ]
    monkeypatch.setattr(v44, "verified_original_cases", lambda report: cases)
    out = v44.build_report(
        {"fingerprint": "pinned-source"}, [{
            "date_et": "2025-06-09", "status": "NO_ALTERNATE",
            "original_expiration": EXP, "original_strike": "100",
        }], [],
    )
    assert out["original_361_pairs_unchanged"] is True
    assert out["actual_historical_profitability"] is None
    assert out["true_historical_signals"] is None
    assert out["oi_recovery_targets"] == 1
    assert out["fingerprint"] == _fingerprint({k:v for k,v in out.items() if k!="fingerprint"})
