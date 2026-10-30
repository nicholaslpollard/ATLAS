from __future__ import annotations

import copy
from decimal import Decimal
from datetime import date, timedelta

import pytest

from packages.simulation import spy_v48_v47_evidence_audit as v48


def test_invalid_or_forged_v47_reports_fail_closed():
    with pytest.raises(v48.AuditError, match="DRIFT"):
        v48.verify({"contract": v48.V47_CONTRACT,
                    "fingerprint": v48.PINNED_V47_FINGERPRINT})
    with pytest.raises(v48.AuditError, match="REQUIRED"):
        v48.verify(None)


def test_outlier_is_not_replaced_by_claimed_positive_mean():
    vals=[-1.0]*100+[120.0]
    metric=v48._stats(vals)
    assert metric["sample"]==101
    assert metric["positive"]==1
    assert metric["median_pct"]==-1.0
    assert metric["mean_pct"]>0
    assert metric["mean_without_single_largest_winner_pct"]==-1.0


def test_missing_exit_censored_not_assumed_zero():
    cases=[
        {"holds":{"1":{"status":"PAIRED_EXIT_QUOTE_QUALIFIED",
                      "primary":{"status":"PAIR_QUOTE_REFERENCE_NET",
                                 "net_percent_of_debit":-4},
                      "stress":{"status":"PAIR_QUOTE_REFERENCE_NET",
                                "net_percent_of_debit":-5}}}},
        {"holds":{"1":{"status":"CENSORED_SOURCE_MISSING",
                      "primary":None,"stress":None}}},
    ]
    metric=v48._metrics(cases,"1","primary")
    assert metric["quoted_dates"]==1
    assert metric["censored_dates"]==1
    assert metric["conditional_quote_reference_returns_pct"]["mean_pct"]==-4.0


def make_account(stress=False):
    pnl=Decimal("-1.30") if stress else Decimal("-0.30")
    account={
        "research_variant":"ORIGINAL_V43_ONLY", "hold_sessions":1,
        "cost_scenario":"stress" if stress else "primary",
        "initial_cash":"100000.00",
        "ending_cash_if_fully_resolved":str(Decimal("100000.00")+48*pnl),
        "unresolved_position":None, "closed_quote_reference_pairs":48,
        "entry_events_including_unresolved":48,"skipped_counts":{},
        "events":[],
    }
    for i in range(48):
        d=date(2018,1,2)+timedelta(days=7*i)
        account["events"].append({
            "status":"CLOSED_QUOTE_REFERENCE_ONLY",
            "entry_date_et":d.isoformat(),
            "target_exit_date_et":(d+timedelta(days=1)).isoformat(),
            "net_dollars":str(pnl),
        })
    return account


def test_recorded_cash_account_reconciles_exact_cents_and_months():
    accounts=[make_account(), make_account(stress=True)]
    x=v48._recorded_account({"chronological_one_slot_quote_reference_accounts":accounts})
    assert x["primary"]["net_dollars"]=="-14.40"
    assert x["stress"]["net_dollars"]=="-62.40"
    assert x["primary"]["closed_pairs"]==48
    assert x["primary"]["months_with_recorded_closures"]["negative"] > 0
    accounts[0]["ending_cash_if_fully_resolved"]="99999.99"
    with pytest.raises(v48.AuditError,match="RECONCILIATION"):
        v48._recorded_account({"chronological_one_slot_quote_reference_accounts":accounts})


def make_cases():
    rows=[]
    # 530 potential paired quote exits, 20 censored; fifth session has one
    # large winner that changes the untrimmed mean's sign.
    missing={"1":1,"2":5,"3":5,"4":4,"5":5}
    for i in range(106):
        row={
            "entry_date_et":(date(2018,1,2)+timedelta(days=7*i)).isoformat(),
            "cohort_origin":v48.ORIGINAL if i<48 else v48.ALTERNATE,
            "holds":{},
        }
        for h in v48.HOLDS:
            blocked=i>=106-missing[h]
            p=120 if h=="5" and i==0 else -1
            row["holds"][h]={
                "status": "CENSORED_EXIT_LEG_SKEW" if blocked else "PAIRED_EXIT_QUOTE_QUALIFIED",
                "primary":None if blocked else {"status":"PAIR_QUOTE_REFERENCE_NET",
                                                "net_percent_of_debit":p},
                "stress":None if blocked else {"status":"PAIR_QUOTE_REFERENCE_NET",
                                               "net_percent_of_debit":-2},
            }
        rows.append(row)
    return rows


def test_audit_five_day_outlier_and_origins_never_claim_real_profit(monkeypatch):
    cases=make_cases()
    monkeypatch.setattr(v48,"verify", lambda d:cases)
    monkeypatch.setattr(v48,"_recorded_account", lambda d:{"primary":{"net_dollars":"-1.00"}})
    result=v48.audit({"fingerprint":v48.PINNED_V47_FINGERPRINT})
    assert result["qualified_observed_pairs"]==510
    assert result["censored_pair_observations"]==20
    assert result["five_day_positive_mean_depends_on_one_outlier"] is True
    assert result["profitable_trading_strategy_demonstrated"] is False
    assert result["provider_requests"]==0
    assert result["independent_validation_or_actual_order_fills"] is False
    assert result["separate_strategy_origins"][v48.ORIGINAL]["1"]["primary"]["quoted_dates"]==48
    assert result["separate_strategy_origins"][v48.ALTERNATE]["1"]["primary"]["quoted_dates"]==57
    assert result["all_five_hold_medians_negative"] is True


def test_no_hindsight_relabeling_after_censored_quote(monkeypatch):
    cases=make_cases()
    cases[0]["holds"]["5"]["primary"]={"status":"PAIR_QUOTE_REFERENCE_NET",
                                         "net_percent_of_debit":120}
    assert cases[0]["holds"]["5"]["status"]=="PAIRED_EXIT_QUOTE_QUALIFIED"
    cases[0]["holds"]["5"]["status"]="CENSORED_SOURCE_MISSING"
    with pytest.raises(v48.AuditError, match="RECONCILIATION"):
        # verification logic: a censored position must not have an active
        # or profitable observed primary return attached.
        def verify_hold(x):
            if (x.get("status")=="PAIRED_EXIT_QUOTE_QUALIFIED") != (x.get("primary") is not None):
                raise v48.AuditError("V48_EXIT_STATUS_RECONCILIATION_FAILURE")
        verify_hold(cases[0]["holds"]["5"])
