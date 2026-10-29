from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_dynamic_source_acquisition_v40 import (
    PretradeSourceDemandError, count_source_observation,
    source_demands_for_entries, source_evidence_summary,
    validate_v37_source_packet,
)
from packages.data.options_native_spy_pretrade_feature_bridge_v37 import CONTRACT as V37_CONTRACT, PINNED_TAPE_FINGERPRINT
from packages.strategies.options_native_pilot_v1_contract import SPECIFICATION_FINGERPRINT


class FakeCalendar:
    def is_session(self, d):
        return True

    def sessions_in_range(self, start, end):
        return [end]


def candidate(day="2019-06-03", strike="275.5"):
    return {
        "original_entry_date_et": day,
        "frozen_expiration_et": (date.fromisoformat(day) + timedelta(days=35)).isoformat(),
        "frozen_strike": strike,
        "historical_source_qualified_1001_order_fill": False,
        "forecast_source_historical_pit_qualified": False,
        "american_call_iv": None,
        "american_put_iv": None,
        "frozen_pilot_entry_signal": None,
        "implied_pair_variance": None,
    }


def packet():
    rows = [candidate((date(2018,1,1) + timedelta(days=i)).isoformat())
            for i in range(361)]
    out = {
        "contract": V37_CONTRACT,
        "status": "SOURCE_BOUND_HISTORICAL_PRETRADE_FEATURE_GAP_PACKET_NOT_SIGNAL",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "source_v32_quote_tape_fingerprint": PINNED_TAPE_FINGERPRINT,
        "original_weekly_decision_clocks": 411,
        "source_selected_pairs": 361,
        "original_abstentions": 50,
        "selected_retrospective_window_present": 358,
        "selected_retrospective_window_missing": 3,
        "qualified_real_historical_volatility_signals": 0,
        "historical_publication_clocks_qualified": False,
        "trading_pnl_computed": False,
        "protected_2026_outcomes_read": 0,
        "entries": rows,
    }
    out["fingerprint"] = _fingerprint(out)
    return out


def test_v37_contract_and_report_fingerprint_qualified_before_fetch():
    p=packet()
    assert len(validate_v37_source_packet(p)) == 361
    p["entries"][0]["frozen_strike"]="1"
    with pytest.raises(PretradeSourceDemandError, match="SHA"):
        validate_v37_source_packet(p)


def test_rejects_unproven_forecast_or_missing_entry():
    p=packet()
    p["entries"][0]["frozen_pilot_entry_signal"]=True
    p["fingerprint"]=_fingerprint({k:v for k,v in p.items() if k!="fingerprint"})
    with pytest.raises(PretradeSourceDemandError, match="PROMOTED"):
        validate_v37_source_packet(p)
    p=packet()
    p["original_abstentions"]=49
    p["fingerprint"]=_fingerprint({k:v for k,v in p.items() if k!="fingerprint"})
    with pytest.raises(PretradeSourceDemandError, match="AUTHORITY"):
        validate_v37_source_packet(p)


def test_three_demand_sources_per_selected_week_clock():
    needs=list(source_demands_for_entries([candidate()],calendar=FakeCalendar()))
    assert len(needs) == 3
    oi,call,put=needs
    assert oi["method"]=="option_history_open_interest_surface"
    assert oi["kwargs"]["date_et"] == "2019-06-02"
    assert oi["kwargs"]["right"] == "both"
    assert oi["kwargs"]["max_dte"] == 75
    assert call["method"]==put["method"]=="option_at_time_quote"
    assert call["kwargs"]["time_of_day_et"] == "10:01:00.000"
    assert put["kwargs"]["time_of_day_et"] == "10:01:00.000"
    assert {call["kwargs"]["right"],put["kwargs"]["right"]} == {"call","put"}
    assert call["kwargs"]["strike"] == "275.5"
    assert all(n["candidate_id"]==oi["candidate_id"] for n in needs)


def test_new_candidate_roster_can_expand_beyond_361_without_request_quota():
    rows=[candidate((date(2018,1,1)+timedelta(days=i)).isoformat())
          for i in range(480)]
    requests=list(source_demands_for_entries(rows,calendar=FakeCalendar()))
    assert len(requests)==480*3
    assert len({(x["candidate_id"],x["purpose"]) for x in requests})==len(requests)


def test_duplicates_and_noncausal_contraints_raise():
    with pytest.raises(PretradeSourceDemandError,match="SESSION"):
        list(source_demands_for_entries([candidate(),candidate()],calendar=FakeCalendar()))
    with pytest.raises(PretradeSourceDemandError,match="SESSION"):
        list(source_demands_for_entries([
            candidate(day="2019-06-03",strike="0")
        ],calendar=FakeCalendar()))


def test_source_evidence_is_source_only_not_trade_or_iv():
    counts=Counter()
    entry=candidate()
    need=list(source_demands_for_entries([entry],calendar=FakeCalendar()))[1]
    counter_source={
        "status":"FETCHED_AND_ARCHIVED",
        "source_rows":(
            {"symbol":"SPY","expiration":need["kwargs"]["expiration"],
             "strike":need["kwargs"]["strike"],"right":"call",
             "bid":0.9,"ask":1.1},
            {"symbol":"SPY","expiration":"2030-01-01",
             "strike":"1","right":"put","bid":0.1,"ask":0.2},
        ),
    }
    count_source_observation(need,counter_source,counts)
    assert counts["exact_contract_present_call_1001_quote"]==1
    assert counts["archived_rows_call_1001_quote"]==2
    report=packet()
    acquisition={
        "status":"ALL_REQUESTED_SOURCES_PRESENT",
        "source_uses_requested":1,
        "source_uses_resolved":1,
        "source_uses_explicit_no_data":0,
        "source_uses_failed_or_unresolved":0,
        "provider_dispatch_attempts":1,
        "provider_fetch_successes":1,
        "persisted_cache_hits":0,
        "exact_query_store":"external_immutable_cache",
    }
    out=source_evidence_summary(report,acquisition,counts)
    assert out["call_put_iv_model_qualified"] is False
    assert out["historical_option_fill_evidence"] is None
    assert out["actual_historical_profitability"] is None
    assert out["source_demand_counts"]["provider_dispatch_attempts"]==1
    assert out["fingerprint"]==_fingerprint({k:v for k,v in out.items() if k!="fingerprint"})
