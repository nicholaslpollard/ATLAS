from __future__ import annotations

"""V88: preregistered, source-bound full-year 2024 historical regime challenge."""

import json
from unittest.mock import patch

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v82_causal_entry_family_registry import REGISTRY
from packages.simulation.spy_v84_offline_three_family_economics import signed, verified
from scripts import run_spy_v88_frozen_2024_regime_challenge as v88


def _synthetic_campaign(*, outside_window=False):
    cases=[
        {"session":"2024-01-02","strategy":"failed_breakout_fade_0940",
         "status":"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED" if i<207 else "NO_SIGNAL"}
        for i in range(756)
    ]
    entry=signed({
        "contract":"atlas-v83-original-native-three-entry-family-source-screen-v2",
        "start":"2024-01-01",
        "end":"2025-01-01" if outside_window else "2024-12-31",
        "cases":cases,"families":REGISTRY,
        "registry_sha":_fingerprint(REGISTRY),
        "xnys_sessions":252,"actual_broker_orders":0,
    })
    plans=[{"kwargs":{"date_et":"2024-01-02"}} for _ in range(207)]
    plan=signed({"demands":plans})
    pre=signed({
        "contract":"atlas-v83-original-native-three-entry-family-source-screen-v2-summary-v1",
        "sessions":252,"broker_orders":0,"actual_fills":0,
        "entry_dispositions":{"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED":207,
                              "NO_SIGNAL":549},
        "source_receipt_report_sha":"synthetic-receipts-fingerprint",
        "source_resolution":{"status":"ALL_REQUESTED_SOURCES_PRESENT"},
    })
    return entry,plan,pre,dict(enumerate(plans)),dict(enumerate(plans))


def _synthetic_roots(campaign):
    entry,plan,pre,_,_=campaign
    return {"entry":entry["fingerprint"],
            "plan":plan["fingerprint"],
            "receipts":pre["source_receipt_report_sha"],
            "summary":pre["fingerprint"]}


def test_v88_original_2024_source_sha_roots_are_explicit_and_pinned():
    assert v88.EXPECTED_ORIGINAL_SHAS == {
        "entry":"f24ecbcc9c7a7c3f22200048b33a8631daeb2121b6ec0b3bc9283b997818f32e",
        "plan":"6d81364b40587d69361241fb1c6b955a0ed19e578e1dd88c6c23e88909dfaf41",
        "receipts":"fdf9ebfc10583febb53b9199fd7b257a2e5615140d80b26fa66e473511f04db3",
        "summary":"c08008c476cdd90eb8fee33749af2c3b64780e4ce4c1098f3bd317caa967d1d9",
    }
    assert v88.PRIMARY == {
        "scope":"failed_breakout_fade_0940",
        "policy":"balanced_35_100",
        "lag_seconds":3,
        "limit_rest_seconds":10,
    }


def test_v88_preflight_frozen_252_days_756_decisions_207_sources(tmp_path):
    folder=tmp_path/"original";folder.mkdir()
    camp=_synthetic_campaign()
    with patch.object(v88,"_load_campaign",return_value=camp), \
         patch.object(v88,"EXPECTED_ORIGINAL_SHAS",_synthetic_roots(camp)):
        entry,pre=v88.preflight(folder)
    assert verified(entry) and verified(pre)
    assert len(entry["cases"])==756


def test_v88_preflight_rejects_modified_source_sha_before_outputs(tmp_path):
    folder=tmp_path/"original";folder.mkdir()
    camp=_synthetic_campaign()
    with patch.object(v88,"_load_campaign",return_value=camp):
        with pytest.raises(v88.V88Error,match="MANIFEST_SHA_CHANGED"):
            v88.preflight(folder)


def test_v88_preflight_rejects_out_of_period_data_even_when_resigned(tmp_path):
    folder=tmp_path/"original";folder.mkdir()
    camp=_synthetic_campaign(outside_window=True)
    with patch.object(v88,"_load_campaign",return_value=camp), \
         patch.object(v88,"EXPECTED_ORIGINAL_SHAS",_synthetic_roots(camp)):
        with pytest.raises(v88.V88Error,match="FROZEN_2024"):
            v88.preflight(folder)


def test_v88_predeclared_primary_persists_when_negative_and_other_scope_positive(tmp_path):
    entry,plan,pre,_,_=_synthetic_campaign()
    source=tmp_path/"original";source.mkdir()
    output=tmp_path/"regime"
    calls=[]
    def fake_v84(src,out):
        calls.append("v84")
        out.mkdir()
        return signed({
            "candidate_sources":207,"trial_count":1242,
            "parent_v83_summary_sha":pre["fingerprint"],
            "provider_requests":0,"broker_orders":0,
        })
    def fake_v85(src,old,out):
        calls.append("v85")
        out.mkdir()
        return signed({
            "original_signed_option_candidates":207,
            "original_sha_verified_trial_journals":1242,
            "portfolio_scenarios":48,
            "provider_requests":0,"broker_orders":0,
        })
    def fake_v86(src,old,out):
        calls.append("v86")
        out.mkdir()
        comparison=signed({
            "contract":"atlas-v86-source-first-exit-order-recheck-and-cash-stress-v1-portfolio-compare-v1",
            "scenarios":[{
                **v88.PRIMARY,
                "shared_cash_quote_reference_pnl_usd":"-100.00",
                "shared_cash_2pct_exit_haircut_quote_reference_pnl_usd":"-123.45",
                "unresolved_exit_actions":0,
                "portfolio_cash_ledger_computable":True,
                "historical_broker_fills_verified":0,
            },{
                "scope":"all_families","policy":"runner_35_150",
                "lag_seconds":1,"limit_rest_seconds":0,
                "shared_cash_2pct_exit_haircut_quote_reference_pnl_usd":"99999.00",
            }],
        })
        (out/"portfolio_comparisons.json").write_text(json.dumps(comparison))
        return signed({
            "original_sha_verified_option_tapes":207,
            "original_sha_verified_v84_trials":1242,
            "v86_recheck_journals":4968,
            "portfolio_scenarios":96,
            "portfolio_comparisons_sha":comparison["fingerprint"],
            "provider_calls":0,"broker_orders":0,
        })
    with patch.object(v88,"preflight",return_value=(entry,pre)):
        result=v88.run(source,output,v84_runner=fake_v84,
                       v85_runner=fake_v85,v86_runner=fake_v86,
                       announce=lambda _:None)
    assert verified(result)
    assert result["primary_preregistered_configuration"]==v88.PRIMARY
    assert result["primary_2pct_haircut_quote_reference_pnl_usd"]=="-123.45"
    assert result["historical_regime_challenge_not_forward_validation"]
    assert result["strategy_not_promoted"]
    assert result["master_holdout_accessed"] is False
    assert result["v86_source_linked_order_rechecks"]==4968
    assert result["actual_broker_fills_verified"]==0
    assert calls==["v84","v85","v86"]
    assert (output/"regime_challenge_summary.json").is_file()


def test_v88_immutable_preexisting_output_rejected_before_inputs(tmp_path):
    source=tmp_path/"original";source.mkdir()
    output=tmp_path/"existing";output.mkdir()
    with pytest.raises(v88.V88Error,match="OUTPUT_ALREADY_EXISTS"):
        v88.run(source,output)
