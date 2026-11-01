from __future__ import annotations

"""V87 contract and freeze tests: synthetic evidence, no provider data."""

from pathlib import Path
from unittest.mock import patch

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v82_causal_entry_family_registry import REGISTRY
from packages.simulation.spy_v84_offline_three_family_economics import signed,verified
from scripts import run_spy_v87_frozen_2026_janapr_validation as v87


def fixture_campaign(*,bad_date=False):
    cases=[
        {"session":"2026-01-05","strategy":x,
         "status":"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED" if i<77 else "NO_SIGNAL"}
        for i,x in enumerate(["failed_breakout_fade_0940"]*77+
                             ["orb_continuation_0940"]*169)
    ]
    entry=signed({
        "contract":"atlas-v83-original-native-three-entry-family-source-screen-v2",
        "start":"2026-01-01",
        "end":"2026-05-31" if bad_date else "2026-04-30",
        "cases":cases,"families":REGISTRY,
        "registry_sha":_fingerprint(REGISTRY),
        "xnys_sessions":82,"actual_broker_orders":0,
    })
    prior=signed({
        "contract":"atlas-v83-original-native-three-entry-family-source-screen-v2-summary-v1",
        "sessions":82,"broker_orders":0,"actual_fills":0,
        "entry_dispositions":{"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED":77},
        "source_resolution":{"status":"ALL_REQUESTED_SOURCES_PRESENT"},
    })
    plans=[{"kwargs":{"date_et":"2026-01-06"}} for _ in range(77)]
    return entry,{"demands":plans},prior,dict(enumerate(plans)),dict(enumerate(plans))


def test_preflight_requires_frozen_calendar_and_source_census(tmp_path):
    directory=tmp_path/"original";directory.mkdir()
    fixture=fixture_campaign()
    with patch.object(v87,"_load_campaign",return_value=fixture):
        entry,prior=v87.preflight(directory)
    assert verified(entry) and verified(prior)
    assert len(entry["cases"])==246


def test_preflight_rejects_protected_holdout_overlap_before_outputs(tmp_path):
    directory=tmp_path/"original";directory.mkdir()
    with patch.object(v87,"_load_campaign",return_value=fixture_campaign(bad_date=True)):
        with pytest.raises(v87.V87Error,match="FROZEN_2026"):
            v87.preflight(directory)


def test_frozen_primary_is_selected_once_not_optimized_after_result(tmp_path):
    entry,plan,prior,demands,receipts=fixture_campaign()
    original_dir=tmp_path/"original";original_dir.mkdir()
    output=tmp_path/"v87"
    price="-126.44"
    calls=[]
    def fake_84(source,out):
        calls.append(("v84",source))
        out.mkdir()
        return signed({
            "candidate_sources":77,"trial_count":462,
            "parent_v83_summary_sha":prior["fingerprint"],
            "provider_requests":0,"broker_orders":0,
        })
    def fake_85(source,old,out):
        calls.append(("v85",source,old))
        out.mkdir()
        return signed({
            "original_signed_option_candidates":77,
            "original_sha_verified_trial_journals":462,
            "portfolio_scenarios":48,
            "provider_requests":0,"broker_orders":0,
        })
    def fake_86(source,old,out):
        calls.append(("v86",source,old))
        out.mkdir()
        comparison=signed({
            "contract":"atlas-v86-source-first-exit-order-recheck-and-cash-stress-v1-portfolio-compare-v1",
            "scenarios":[{
                **v87.PRIMARY,
                "shared_cash_quote_reference_pnl_usd":"-100.00",
                "shared_cash_2pct_exit_haircut_quote_reference_pnl_usd":price,
                "unresolved_exit_actions":0,
                "portfolio_cash_ledger_computable":True,
                "historical_broker_fills_verified":0,
            },{
                "scope":"all_families","policy":"runner_35_150",
                "lag_seconds":1,"limit_rest_seconds":0,
                "shared_cash_2pct_exit_haircut_quote_reference_pnl_usd":"+99999.00",
            }]
        })
        import json
        (out/"portfolio_comparisons.json").write_text(json.dumps(comparison))
        return signed({
            "original_sha_verified_option_tapes":77,
            "original_sha_verified_v84_trials":462,
            "v86_recheck_journals":1848,
            "portfolio_scenarios":96,
            "portfolio_comparisons_sha":comparison["fingerprint"],
            "provider_calls":0,"broker_orders":0,
        })
    with patch.object(v87,"preflight",return_value=(entry,prior)):
        evidence=v87.run(original_dir,output,
            v84_runner=fake_84,v85_runner=fake_85,v86_runner=fake_86,
            announce=lambda _:None)
    assert verified(evidence)
    assert evidence["primary_preregistered_configuration"]==v87.PRIMARY
    assert evidence["primary_2pct_haircut_quote_reference_pnl_usd"]==price
    assert evidence["strategy_not_promoted"] is True
    assert evidence["master_holdout_accessed"] is False
    assert evidence["v86_source_linked_order_rechecks"]==1848
    assert [x[0] for x in calls]==["v84","v85","v86"]
    assert (output/"validation_summary.json").is_file()
    assert evidence["actual_broker_fills_verified"]==0


def test_existing_immutable_output_rejected_before_reading_any_source(tmp_path):
    source=tmp_path/"source";source.mkdir()
    output=tmp_path/"already_exists";output.mkdir()
    with pytest.raises(v87.V87Error,match="OUTPUT_ALREADY_EXISTS"):
        v87.run(source,output)
