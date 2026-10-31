from __future__ import annotations

from datetime import date
import json

import pytest

from scripts import run_spy_v77_multi_month_source_and_exit_campaign as v77
from scripts import run_spy_v76_registered_exit_benchmark as v76


def mock_source(first,last,folder):
    folder.mkdir(parents=True,exist_ok=False)
    payload={"contract":v77.V69,
             "original_preflight_sha":"f"*64,
             "runtime_source_receipt":{
                 "source_uses_requested":12,
                 "provider_dispatch_attempts":3,
                 "persisted_cache_hits":9,
                 "source_uses_explicit_no_data":0,
             }}
    receipt=v77.signature(payload)
    (folder/"chunk_0001.sources.json").write_text(json.dumps(receipt),encoding="utf8")
    return v77.signature({
        "contract":v77.V69,
        "broker_orders":0,"chunks":1,
        "chunk_summaries":[{"status":"SOURCE_CHECKED_AND_REPLAYED"}],
        "status":"COMPLETE_SOURCE_CENSUS_WITH_OPEN_POSITIONS",
        "start":first.isoformat(),"end":last.isoformat(),
    })


def mock_exit(folder,out,*,expected_parent_sha):
    assert len(expected_parent_sha)==64
    assert (folder/"chunk_0001.sources.json").is_file()
    out.mkdir(parents=True,exist_ok=False)
    return v77.signature({
        "contract":v76.CONTRACT,
        "provider_calls":0,"broker_orders":0,
        "policies":[{
            "name":name,"lag_seconds":lag,
            "closed_trade_count":1,
            "modeled_closed_trade_pnl":"-12.30",
            "unresolved_days":[],
        } for name in v76.POLICIES for lag in v76.LAGS],
    })


def test_one_command_month_batch_preserves_source_counts_and_policy_registry(tmp_path):
    messages=[]
    result=v77.run(date(2025,7,1),date(2025,8,1),
                   tmp_path/"campaign",source_run=mock_source,
                   benchmark_run=mock_exit,emit=messages.append)
    assert result["status"]=="COMPLETE_ALL_MONTHS_QUOTE_REFERENCE_ONLY"
    assert result["months_requested"]==result["months_processed"]==2
    assert result["provider_dispatches_in_confirmed_month_receipts"]==6
    assert not result["provider_requests_unknown_for_blocked_stages"]
    assert len(result["aggregate_of_closed_trade_subset_not_true_account_cash"])==10
    assert result["broker_orders"]==result["real_option_broker_fills"]==0
    assert all(m["source_uses_requested"]==12 for m in result["months"])
    assert all(m["persisted_cache_hits"]==9 for m in result["months"])
    assert all(m["status"]=="EXIT_MATRIX_ALL_QUOTE_CASES_RESOLVED" for m in result["months"])
    assert any(m.startswith("STAGE_START V77") for m in messages)
    assert any(m.startswith("PROGRESS_10PCT V77") for m in messages)
    assert any(m.startswith("PROGRESS_100PCT V77") for m in messages)
    assert messages[-1].startswith("COMPLETE V77")
    assert (tmp_path/"campaign"/"summary.json").is_file()
    assert len(list((tmp_path/"campaign").glob("month_*.receipt.json")))==2


def test_unrelated_month_still_runs_after_independent_month_failure(tmp_path):
    calls=[]
    def flaky_benchmark(parent,out,*,expected_parent_sha):
        calls.append(parent.name)
        if parent.name.startswith("202507"):
            raise RuntimeError("synthetic exact source tape error")
        return mock_exit(parent,out,expected_parent_sha=expected_parent_sha)
    doc=v77.run(date(2025,7,1),date(2025,8,1),
                tmp_path/"out",source_run=mock_source,
                benchmark_run=flaky_benchmark,emit=lambda _m:None)
    assert len(calls)==2
    assert doc["status"]=="COMPLETE_WITH_EXPLICIT_MONTH_BLOCKERS"
    assert doc["blocked_months"]==["202507"]
    assert doc["months"][0]["error_class"]=="RuntimeError"
    assert doc["months"][1]["status"]=="EXIT_MATRIX_ALL_QUOTE_CASES_RESOLVED"
    assert doc["broker_orders"]==0


def test_invalid_roster_or_preexisting_output_fails_before_any_provider(tmp_path):
    assert v77.month_starts(date(2025,12,1),date(2026,2,1))==[
        date(2025,12,1),date(2026,1,1),date(2026,2,1)]
    with pytest.raises(ValueError,match="MONTH_RANGE_INVALID"):
        v77.month_starts(date(2025,7,2),date(2025,8,1))
    with pytest.raises(ValueError,match="MONTH_RANGE_INVALID"):
        v77.month_starts(date(2025,8,1),date(2025,7,1))
    already=tmp_path/"exists"
    already.mkdir()
    with pytest.raises(ValueError,match="OUTPUT_OR_EMPTY_RANGE"):
        v77.run(date(2025,7,1),date(2025,8,1),already,
                source_run=lambda *a:pytest.fail("no provider"),
                emit=lambda _:None)


def test_source_summary_signature_ambiguity_prevents_exit_but_allows_other_month(tmp_path):
    def corrupted_source(first,last,folder):
        doc=mock_source(first,last,folder)
        if first.month==7:
            doc["fingerprint"]="0"*64
        return doc
    invoked=[]
    def safe_exit(parent,out,*,expected_parent_sha):
        invoked.append(parent.name)
        return mock_exit(parent,out,expected_parent_sha=expected_parent_sha)
    doc=v77.run(date(2025,7,1),date(2025,8,1),
                tmp_path/"out",source_run=corrupted_source,
                benchmark_run=safe_exit,emit=lambda _:None)
    assert invoked==["202508_v73_original_sources"]
    assert doc["blocked_months"]==["202507"]
    assert doc["months"][0]["status"]=="MONTH_EXECUTION_OR_SOURCE_BLOCKED"
