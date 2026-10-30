from __future__ import annotations

from decimal import Decimal
import copy

import pytest

from packages.simulation import spy_v47_counterfactual_quote_exit as v47


def _leg(bid=4.0, ask=4.2):
    return {"status":"QUOTE_MICROSTRUCTURE_PASSES", "bid":bid, "ask":ask,
            "timestamp_et":"2023-06-06T10:00:59-04:00"}


def _source(day="2023-06-05"):
    return {"date_et":day, "cohort_origin":"ORIGINAL_V43",
            "expiration":"2023-07-07", "strike":"420",
            "quote_quality":{"execution_1001":{
                "call":_leg(4,4.2), "put":_leg(3,3.2), "skew_seconds":0.0
            }}, "status":"TWO_CLOCK_SOURCE_QUALITY_PASSES"}


class Calendar:
    def sessions_in_range(self, begin, end):
        from datetime import timedelta
        return [begin + timedelta(days=n) for n in range(15)]
    def is_session(self, day):
        return True


def _pair(hold=1, entry_day="2023-06-05"):
    exitq={"status":"PAIRED_EXIT_QUOTE_QUALIFIED",
           "call":_leg(5,5.2), "put":_leg(4,4.2), "skew_seconds":0.0}
    quote={"call":_leg(4,4.2), "put":_leg(3,3.2), "skew_seconds":0}
    return {"entry_date_et":entry_day, "cohort_origin":"ORIGINAL_V43",
            "entry_quote":quote, "holds":{str(hold):{
                "status":"PAIRED_EXIT_QUOTE_QUALIFIED",
                "exit_date_et":"2023-06-06", "exit_quote":exitq,
                "primary":v47._quote_pnl(quote,exitq),
                "stress":v47._quote_pnl(quote,exitq,stressed=True),
            }}}


def test_next_sessions_are_exchange_calendar_holiday_aware():
    dates=v47.exit_sessions("2023-07-03")
    assert dates[1]=="2023-07-05"
    assert dates[2]=="2023-07-06"


def test_only_selected_dates_emit_five_sessions_both_rights():
    plan=v47.build_plan([_source()],calendar=Calendar())
    demands=list(v47.exit_demands(plan))
    assert len(demands)==10
    assert {x["kwargs"]["right"] for x in demands}=={"call","put"}
    assert {x["kwargs"]["time_of_day_et"] for x in demands}=={"10:01:00.000"}
    assert {x["purpose"] for x in demands}=={
        f"s{s}_{right}_1001" for s in range(1,6) for right in ("call","put")
    }
    assert {x["kwargs"]["expiration"] for x in demands}=={"2023-07-07"}
    assert {x["kwargs"]["strike"] for x in demands}=={"420"}


def test_censored_exit_absence_does_not_infer_zero():
    assert v47._pair_quote_exit({},1)=={"status":"CENSORED_SOURCE_MISSING"}


def test_unqualified_one_leg_censors_entire_pair(monkeypatch):
    def parsed(source, demand):
        return {"status":"QUOTE_REJECTED"}
    monkeypatch.setattr(v47,"_exact_quote",parsed)
    source={"s1_call_1001":({"kwargs":{}},{"status":"FETCHED_AND_ARCHIVED"}),
            "s1_put_1001":({"kwargs":{}},{"status":"FETCHED_AND_ARCHIVED"})}
    assert v47._pair_quote_exit(source,1)["status"]=="CENSORED_EXIT_QUOTE_UNQUALIFIED"


def test_skew_censors_two_leg_exit(monkeypatch):
    def parsed(source, demand):
        return {"status":"QUOTE_MICROSTRUCTURE_PASSES",
                "timestamp_et":"2023-06-06T10:00:58-04:00" if demand["kwargs"]["right"]=="call"
                               else "2023-06-06T10:00:56-04:00"}
    monkeypatch.setattr(v47,"_exact_quote",parsed)
    sources={f"s1_{r}_1001":({"kwargs":{"right":r}},{"status":"CACHE_HIT"})
             for r in ("call","put")}
    assert v47._pair_quote_exit(sources,1)["status"]=="CENSORED_EXIT_LEG_SKEW"


def test_quote_net_cost_and_spread_stress_are_distinct_from_fills():
    p=_pair()
    primary=p["holds"]["1"]["primary"]
    stress=p["holds"]["1"]["stress"]
    assert primary["entry_debit_plus_fees"]=="741.30"
    assert primary["exit_credit_less_fees"]=="898.70"
    assert primary["net_dollars_one_pair"]=="157.40"
    assert Decimal(stress["net_dollars_one_pair"]) < Decimal(primary["net_dollars_one_pair"])
    assert primary["price_source_is_broker_fill"] is False


def test_one_slot_account_with_censored_exit_remains_unresolved():
    first=_pair()
    first["holds"]["1"].update({"status":"CENSORED_SOURCE_MISSING",
                                  "exit_quote":None,"primary":None,"stress":None})
    second=_pair(entry_day="2023-06-12")
    account=v47._account_scenario([first,second],1,"primary")
    assert account["ending_cash_if_fully_resolved"] is None
    assert account["unresolved_position"]["exit_status"]=="CENSORED_SOURCE_MISSING"
    assert account["skipped_counts"]["UNRESOLVED_POSITION_BLOCKS_LATER_ENTRIES"]==1
    assert account["entry_events_including_unresolved"]==1


def test_quote_account_closed_has_costs_and_no_trading_claim():
    account=v47._account_scenario([_pair()],1,"primary")
    assert account["ending_cash_if_fully_resolved"]=="100157.40"
    assert account["closed_quote_reference_pairs"]==1
    assert account["historical_execution_or_true_strategy_pnl"] is False


def test_five_percent_cap_skips_expensive_quote_reference():
    p=_pair()
    p["entry_quote"]["call"]["ask"]=60
    account=v47._account_scenario([p],1,"primary")
    assert account["entry_events_including_unresolved"]==0
    assert account["skipped_counts"]["FIVE_PERCENT_DEBIT_CAP"]==1


def test_strict_pin_rejects_any_noncurrent_or_tampered_v46_v45():
    with pytest.raises(v47.V47Error,match="FINGERPRINT"):
        v47.verified_cases({}, {})
    with pytest.raises(v47.V47Error,match="FINGERPRINT"):
        v47._check({"contract":"x","fingerprint":"0"*64},"x","0"*64)
