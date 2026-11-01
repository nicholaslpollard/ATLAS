from __future__ import annotations

"""Synthetic, SHA-ledger-only V100 prior-fold tests; no provider or broker."""
from decimal import Decimal
import json
from pathlib import Path

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts import run_spy_v100_v99_independent_wfo_audit as v100


def cell(value,*,wins=5,losses=5,qualified=True):
    return {
        "cash_equity_known":qualified,
        "quote_pnl_if_complete_usd":str(value) if qualified else None,
        "simulated_closed_wins":wins,"simulated_closed_losses":losses,
        "source_complete":qualified,
        "monthly_stressed_pnl_usd":{},
        "weekly_stressed_pnl_usd":{},
    }


def key(name):
    return (name,"balanced_35_100",1,10)


def fake_cases():
    years=v100.DEVELOPMENT
    a={year:cell("100.00" if i<3 else "-200.00")
       for i,year in enumerate(years)}
    b={year:cell("-50.00" if i<3 else "300.00")
       for i,year in enumerate(years)}
    return {key("A"):a,key("B"):b}


def test_v100_registered_training_and_frozen_holdout_sequence():
    assert len(v100.DEVELOPMENT)==8
    assert "2020_SOURCE_PARTIAL" not in v100.DEVELOPMENT
    assert v100.DEVELOPMENT[:3]==("2018_full","2019_full","2021_full")
    assert v100.DEVELOPMENT[3]=="2022_full"
    assert v100.DEVELOPMENT[-1]=="2026_janapr"
    assert v100.MIN_TRAINING_CLOSED_TRADES==10
    assert v100.SELECTORS==(
        "prior_total","prior_profitable_periods","prior_worst_period",
    )


@pytest.mark.parametrize("selector",v100.SELECTORS)
def test_prior_only_selection_ignores_next_period_profitability(selector):
    cases=fake_cases()
    prior=v100.DEVELOPMENT[:3]
    picked,count=v100.pick(cases,prior,selector)
    assert count==2
    assert picked["scenario_id"]["trial_id"]=="A"
    cases[key("A")]["2022_full"]["quote_pnl_if_complete_usd"]="9999999.00"
    cases[key("B")]["2022_full"]["quote_pnl_if_complete_usd"]="-9999999.00"
    again,n=v100.pick(cases,prior,selector)
    assert again==picked and n==count


def test_prior_cash_unknown_rejected_and_does_not_get_negative_zero():
    cases=fake_cases()
    cases[key("A")]["2019_full"]=cell(None,qualified=False)
    picked,n=v100.pick(cases,v100.DEVELOPMENT[:3],"prior_total")
    assert n==1 and picked["scenario_id"]["trial_id"]=="B"
    cases[key("B")]["2021_full"]=cell("100.00",wins=0,losses=0)
    cases[key("B")]["2019_full"]=cell("100.00",wins=0,losses=0)
    cases[key("B")]["2018_full"]=cell("100.00",wins=0,losses=0)
    picked,n=v100.pick(cases,v100.DEVELOPMENT[:3],"prior_total")
    assert picked is None and n==0


def test_rolling_evaluates_only_subsequent_period_and_records_losses():
    cases=fake_cases()
    study=v100.rolling(cases)
    for selector in v100.SELECTORS:
        item=study[selector]
        assert len(item["folds"])==5
        assert item["folds"][0]["next_period"]=="2022_full"
        assert item["folds"][0]["training_periods"]==[
            "2018_full","2019_full","2021_full",
        ]
        assert item["folds"][0]["choice"]["scenario_id"]["trial_id"]=="A"
        assert item["folds"][0]["test_quote_pnl_usd"]=="-200.00"
        assert item["folds"][0]["status"]=="NEXT_PERIOD_COMPLETE_MODEL_QUOTE_RESULT"


def test_unknown_next_period_censors_result_without_automatic_substitution():
    cases=fake_cases()
    cases[key("A")]["2022_full"]=cell(None,qualified=False)
    study=v100.rolling(cases)
    first=study["prior_total"]["folds"][0]
    assert first["status"]=="NEXT_PERIOD_SOURCE_OR_CASH_CENSORED"
    assert first["test_quote_pnl_usd"] is None
    assert study["prior_total"]["full_five_period_quote_pnl_if_all_qualified"] is None
    assert "2022_full" in study["prior_total"]["censored_next_periods"]


def test_decimal_cash_pnl_is_fail_closed_and_signatures_are_strict(tmp_path):
    item={"contract":"test","values":[1,2],"provider_calls":0}
    signed=v100.write_once(tmp_path/"test.json",item)
    assert signed["fingerprint"]==_fingerprint(item)
    assert v100.source(tmp_path/"test.json","test")==signed
    saved=json.loads((tmp_path/"test.json").read_text())
    saved["provider_calls"]=1
    (tmp_path/"test.json").write_text(json.dumps(saved))
    with pytest.raises(v100.V100Error,match="SHA_OR_CONTRACT"):
        v100.source(tmp_path/"test.json","test")
    with pytest.raises(TypeError):
        v100.write_once(tmp_path/"bad.json",{
            "contract":"test","bad_python_decimal":Decimal("9.00"),
        })
    assert not (tmp_path/"bad.json").exists()


def test_original_630_source_journal_manifest_has_to_be_complete(tmp_path):
    with pytest.raises(v100.V100Error,match="630_ORIGINAL_TRIAL_JOURNALS_REQUIRED"):
        v100.source_journal_audit(tmp_path,{
            "total_source_family_journals":1,
            "source_tape_family_journals":[],
        })


def test_user_workstation_full_signed_v99_cash_and_630_journals_if_available():
    root=Path(__file__).resolve().parents[1]/"data"/"research"
    locations=sorted(p for p in root.glob("spy_v99_49_call_quote_cash_campaign_*")
                    if p.is_dir() and (p/"summary.json").is_file()
                    and (p/"journals").is_dir())
    if len(locations)!=1:
        pytest.skip("One complete original V99 quote-journal stage required")
    stage=locations[0]
    summary=v100.source(stage/"summary.json",v100.V99)
    matrix=v100.source(stage/"eight_period_exploratory_matrix.json",
                      v100.V99+"-eight-period-account-robustness-v1")
    manifest=v100.source(stage/"trial_archive_manifest.json",
                        v100.V99+"-signed-trial-archive-manifest-v1")
    cases,audit=v100.verify_every_ledger(stage,summary,matrix,manifest,
                                         full_journals=True)
    assert len(cases)==1200
    assert audit["account_scenarios_sha_verified"]==10800
    assert audit["signed_source_archive_provenance"]["archive_sha_checked"]==630
    assert audit["signed_source_archive_provenance"]["unique_original_historical_query_id"]==576
    assert summary["provider_requests"]==summary["broker_orders"]==0
