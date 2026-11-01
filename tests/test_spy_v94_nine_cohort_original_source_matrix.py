from __future__ import annotations

"""V94 1512-row immutable comparison; all data synthetic, no provider."""

import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import FAMILIES,signed
from packages.simulation.spy_v90_six_family_capital_ledger import SCOPES,signed as sign90
from packages.simulation.spy_v84_offline_three_family_economics import POLICIES,LAGS
from packages.simulation.spy_v86_original_option_exit_recheck import DWELLS
from scripts import run_spy_v94_nine_cohort_original_source_matrix as v94


def save(path,row):
    path.write_text(json.dumps(row,sort_keys=True)+"\n")
    return row


def make(tmp_path,cohort,period,*,make_unresolved=False):
    v89dir=tmp_path/(cohort+"_v89");v89dir.mkdir()
    v90dir=tmp_path/(cohort+"_v90");v90dir.mkdir()
    first,last=period
    entry=save(v89dir/"entry_screen.json",signed({
        "contract":"atlas-v89-six-family-original-source-campaign-v1",
        "start":first,"end":last,"registry":FAMILIES,
        "registry_sha":_fingerprint(FAMILIES),
        "sessions":1,"cases":[{"strategy":f} for f in FAMILIES],
        "source_months":[
            {"year":int(cohort[:4]),"month":m,
             "unit_id":f"unit{cohort[:4]}-{m:02d}",
             "original_stock_sha256":"a"*64,
             "original_raw_bundle_sha256":"b"*64}
            for m in range(1,13)
        ] if cohort.endswith("_full") and int(cohort[:4])<=2023 else [],
    }))
    pre=save(v89dir/"summary.json",signed({
        "contract":"atlas-v89-six-family-original-source-campaign-v1-summary-v1",
        "entry_sha":entry["fingerprint"],
        "source_resolution":{"status":"ALL_REQUESTED_SOURCES_PRESENT"},
        "all_required_sources_archived":True,
        "market_sessions":1,"considered_decisions":len(FAMILIES),
        "exact_source_requirements":2,
        "per_family_dispositions":{f:{"NO_SIGNAL":1} for f in FAMILIES},
    }))
    manifest=save(v90dir/"trial_manifest.json",signed({
        "contract":"atlas-v90-six-new-hypotheses-original-quote-batch-v1-original-signed-trial-manifest-v1",
        "parent_v89_summary_sha":pre["fingerprint"],
        "total_journals":48,
    }))
    ledgers=[]
    for scope in SCOPES:
        for policy in POLICIES:
            for lag in LAGS:
                for dwell in DWELLS:
                    unknown=(make_unresolved and scope==SCOPES[0] and
                             policy=="balanced_35_100" and lag==3 and dwell==10)
                    ledgers.append(sign90({
                        "contract":"atlas-v90-new-six-family-execution-sober-ledger-v1",
                        "scope":scope,"policy":policy,
                        "lag_seconds":lag,"limit_rest_seconds":dwell,
                        "original_opportunities":2,
                        "dispositions":{
                            "HYPOTHETICAL_ENTRY_ASK_DEBIT":1,
                            "CLOSED_HYPOTHETICAL_QUOTE_EXIT":1,
                        },
                        "positive_closed":1,"negative_closed":0,
                        "closed_trade_stressed_quote_pnl_usd":"10.00",
                        "flat_to_flat_max_stressed_drawdown_usd":"0.00",
                        "largest_positive_1_stressed_quote_usd":"10.00",
                        "largest_positive_2_stressed_quote_usd":None,
                        "pnl_excluding_top_two_positive_quote_outcomes_usd":"0.00",
                        "unresolved_exercise_or_expiry_cash":unknown,
                        "terminal_equity_known_if_flat_usd":None if unknown else "25010.00",
                        "actual_broker_orders":0,
                    }))
    books=save(v90dir/"portfolio_ledgers.json",signed({
        "contract":"atlas-v90-six-new-hypotheses-original-quote-batch-v1-full-portfolio-ledgers-v1",
        "parent_original_trial_manifest_sha":manifest["fingerprint"],
        "ledgers":ledgers,"broker_orders":0,
    }))
    save(v90dir/"summary.json",signed({
        "contract":"atlas-v90-six-new-hypotheses-original-quote-batch-v1",
        "parent_v89_entry_sha":entry["fingerprint"],
        "parent_v89_summary_sha":pre["fingerprint"],
        "trial_manifest_sha":manifest["fingerprint"],
        "portfolio_ledgers_sha":books["fingerprint"],
        "signed_quote_trial_journals":48,"broker_orders":0,
    }))
    return v89dir,v90dir



def make_gate(tmp_path):
    gate=tmp_path/"v93";gate.mkdir()
    from packages.simulation.spy_v89_six_family_causal_registry import signed
    doc=signed({
        "contract":"atlas-v93-frozen-original-source-preflight-2018-through-2023-v1",
        "original_v92_inventory_sha":
            "e19d03c45847e48b536d6eab16331aa752ae296b525484693cc210e63528f0e9",
        "full_source_months_sha_reverified":72,
        "month_source_observations":[
            {"year":y,"month":m,"unit_id":f"unit{y}-{m:02d}",
             "canonical_sha256":"a"*64,
             "raw_bundle_sha256":"b"*64}
            for y in range(2018,2024) for m in range(1,13)
        ],
        "provider_calls":0,"broker_orders":0,
    })
    (gate/"preflight.json").write_text(json.dumps(doc))
    return gate


def test_all_1512_matrix_rows_and_unresolved_scenario_are_preserved(tmp_path):
    inputs={
        name:make(tmp_path,name,period,make_unresolved=(name=="2024_full"))
        for name,period in v94.COHORTS.items()
    }
    result=v94.run(inputs,tmp_path/"matrix",v93_preflight_dir=make_gate(tmp_path))
    assert result["total_comparison_rows"]==1512
    assert result["cross_cohort_configurations"]==168
    assert result["complete_nine_cohort_configurations"]==167
    assert result["diagnostic_positive_in_all_nine_cohorts"]==167
    assert result["posthoc_variant_selection_prohibited"] is True
    assert result["protected_2026_master_holdout_accessed"] is False
    rows=json.loads((tmp_path/"matrix"/"full_matrix.json").read_text())["rows"]
    unresolved=[x for x in rows if x["unresolved_exercise_or_expiry_cash"]]
    assert len(unresolved)==1
    assert unresolved[0]["stressed_quote_pnl_usd"] is None
    assert (tmp_path/"matrix"/"full_matrix.csv").is_file()


def test_modified_original_capital_ledger_rejected(tmp_path):
    inputs={
        name:make(tmp_path,name,period)
        for name,period in v94.COHORTS.items()
    }
    bad=inputs["2024_full"][1]/"portfolio_ledgers.json"
    doc=json.loads(bad.read_text())
    doc["ledgers"][0]["closed_trade_stressed_quote_pnl_usd"]="999999.00"
    bad.write_text(json.dumps(doc))
    with pytest.raises(v94.V94Error,match="SIGNED_DOCUMENT_CHANGED"):
        v94.run(inputs,tmp_path/"should_not_exist",v93_preflight_dir=make_gate(tmp_path))
    assert not (tmp_path/"should_not_exist").exists()


def test_original_2022_month_sha_replacement_blocked_even_with_resigned_v89(tmp_path):
    inputs={name:make(tmp_path,name,period) for name,period in v94.COHORTS.items()}
    gate=make_gate(tmp_path)
    old=inputs["2022_full"][0]/"entry_screen.json"
    doc=json.loads(old.read_text())
    doc["source_months"][2]["original_stock_sha256"]="f"*64
    doc={k:v for k,v in doc.items() if k!="fingerprint"}
    from packages.simulation.spy_v89_six_family_causal_registry import signed
    old.write_text(json.dumps(signed(doc)))
    with pytest.raises(v94.V94Error,match="SOURCE_MONTH_SHA_NOT_EQUAL"):
        v94.run(inputs,tmp_path/"blocked",v93_preflight_dir=gate)
    assert not (tmp_path/"blocked").exists()
