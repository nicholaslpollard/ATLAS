from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_additive_2022_campaign_v1 as campaign
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _fake_world(tmp_path, *, total=4, collision=False, loader_calls=None):
    settings = SimpleNamespace(project_root=tmp_path, resolved_path=lambda p: tmp_path / p)
    calls = []
    prepared = []
    remaining = {i: 0 if i == 0 else 40 for i in range(total)}
    def loader(*a, **kw):
        if loader_calls is not None:
            loader_calls.append(1)
        return ("accepted-source", {"source_integrity_fingerprint": "a" * 64})
    def prepare(settings, *, shard_index, duckdb_threads, loader, progress):
        prepared.append(shard_index)
        if shard_index > 0:
            loader(settings.project_root)
        keys = [
            [f"T{shard_index:02d}-{i:02d}", "2022-03-17", "2022-04-14"]
            for i in range(40)
        ]
        if collision and shard_index == 2:
            keys[0] = ["T01-00", "2022-03-17", "2022-04-14"]
        path = settings.resolved_path(f"source-{shard_index}.json")
        path.write_text(json.dumps({
            "shard_index": shard_index, "total_additive_shards": total,
            "all_additive_query_keys_fingerprint": "b" * 64,
            "selected_query_keys": keys,
        }))
        binding = {
            "shard_index": shard_index, "year": 2022,
            "shared_chains": 40, "plan_fingerprint": f"plan-{shard_index}",
            "source_sha256": "c" * 64,
        }
        return {"plan_fingerprint": f"plan-{shard_index}",
                "shared_chain_requests": 40}, path, binding, "REUSED" if not shard_index else "NEW"
    def runner(settings, plan, path, *, max_total_new_requests,
               max_observed_credits, authorize, paid, private, classify_no_data, progress):
        index = int(plan["plan_fingerprint"].split("-")[1])
        used = min(max_total_new_requests, remaining[index])
        remaining[index] -= used
        calls.append((index, max_total_new_requests, max_observed_credits, used))
        if progress:
            progress({"stage": "TEST_BATCH", "new_GETs": used})
        return {
            "new_provider_attempts_this_invocation": used,
            "observed_provider_credits_this_invocation": used,
            "completed_chains": 40 - remaining[index],
            "proven_exact_query_gaps": 0,
            "pending": remaining[index],
            "last_observed_credits_remaining": 9836 - sum(x[3] for x in calls)
                if used else None,
            "report_fingerprint": f"receipt-{index}-{remaining[index]}",
        }
    return settings, prepare, runner, loader, remaining, calls, prepared


def test_first_complete_shard_skipped_then_bounded_resume_and_single_source_load(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda *_: None)
    loads = []
    settings, prepare, runner, loader, rem, calls, prepared = _fake_world(
        tmp_path, total=4, loader_calls=loads,
    )
    result = campaign.run_additive_campaign(
        settings, start_shard=0, max_shards=4, max_total_new_requests=60,
        max_observed_credits=100, authorize=True, paid=True, private=True,
        classify_no_data=True, preparer=prepare, runner=runner, loader=loader,
    )
    assert [(i, n) for i, _, _, n in calls] == [(0, 0), (1, 40), (2, 20)]
    assert result["new_provider_attempts"] == 60
    assert result["status"] == "PARTIAL_CAMPAIGN_BUDGET"
    assert result["shard_reports"][0]["new_provider_attempts"] == 0
    assert result["shard_reports"][-1]["pending"] == 20
    assert result["accepted_source_loads_this_run"] == 1
    assert len(loads) == 1 and prepared == [0, 1, 2]
    resume = campaign.run_additive_campaign(
        settings, start_shard=2, max_shards=2, max_total_new_requests=60,
        max_observed_credits=80, authorize=True, paid=True, private=True,
        preparer=prepare, runner=runner, loader=loader,
    )
    assert resume["status"] == "COMPLETE_CAMPAIGN_RANGE"
    assert resume["new_provider_attempts"] == 60
    assert rem[2] == rem[3] == 0
    assert resume["accepted_source_loads_this_run"] == 1


def test_global_credit_target_stops_before_next_shard(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda *_: None)
    settings, prepare, runner, loader, rem, calls, prepared = _fake_world(tmp_path)
    result = campaign.run_additive_campaign(
        settings, max_shards=4, max_total_new_requests=120,
        max_observed_credits=40, authorize=True, paid=True, private=True,
        preparer=prepare, runner=runner, loader=loader,
    )
    assert result["status"] == "PARTIAL_CAMPAIGN_BUDGET"
    assert prepared == [0, 1]
    assert result["observed_credits"] == 40
    assert calls[-1][0] == 1


def test_frozen_census_and_duplicate_physical_query_fail_before_next_provider_call(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda *_: None)
    settings, prepare, runner, loader, rem, calls, prepared = _fake_world(tmp_path, collision=True)
    with pytest.raises(CandidateChainCacheError, match="duplicate physical"):
        campaign.run_additive_campaign(
            settings, max_shards=3, max_total_new_requests=120,
            authorize=True, paid=True, private=True, preparer=prepare,
            runner=runner, loader=loader,
        )
    assert [x[0] for x in calls] == [0, 1]


def test_frozen_range_and_explicit_authority_checked_before_disk_or_network(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "_require_external",
                        lambda *_: pytest.fail("storage must not be inspected"))
    for kw in (
        {"max_shards": 11},
        {"start_shard": -1},
        {"max_total_new_requests": 401},
        {"max_observed_credits": 501},
        {"max_total_new_requests": 1, "authorize": True, "paid": True},
        {"classify_no_data": True},
    ):
        with pytest.raises(CandidateChainCacheError):
            campaign.run_additive_campaign(object(), **kw)


def test_out_of_census_range_stops_before_any_shard_acquisition(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda *_: None)
    settings, prepare, runner, loader, rem, calls, prepared = _fake_world(tmp_path, total=2)
    with pytest.raises(CandidateChainCacheError, match="range exceeds"):
        campaign.run_additive_campaign(
            settings, start_shard=1, max_shards=2, max_total_new_requests=80,
            authorize=True, paid=True, private=True,
            preparer=prepare, runner=runner, loader=loader,
        )
    assert not calls and prepared == [0]


def test_cache_exception_stops_before_next_shard(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda *_: None)
    settings, prepare, runner, loader, rem, calls, prepared = _fake_world(tmp_path)
    def fail_on_one(*args, **kw):
        index = int(args[1]["plan_fingerprint"].split("-")[1])
        if index == 1:
            raise CandidateChainCacheError("unresolved paid attempt")
        return runner(*args, **kw)
    with pytest.raises(CandidateChainCacheError, match="unresolved paid attempt"):
        campaign.run_additive_campaign(
            settings, max_shards=4, max_total_new_requests=100,
            authorize=True, paid=True, private=True,
            preparer=prepare, runner=fail_on_one, loader=loader,
        )
    assert prepared == [0, 1] and len(calls) == 1
