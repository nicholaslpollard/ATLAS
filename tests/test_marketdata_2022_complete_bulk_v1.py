from __future__ import annotations

"""Offline original-receipt simulations for complete 2022 bulk orchestration."""

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_2022_complete_bulk_v1 as bulk
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _rig(tmp_path, monkeypatch, *, fail_shard=None, low_remaining=False):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    monkeypatch.setattr(bulk, "assert_category_acquisition_allowed", lambda *a, **kw: None)
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    global_fp = "f" * 64
    paths: dict[int, Path] = {}
    for index in range(71):
        count = 12 if index == 70 else 40
        payload = {
            "total_additive_shards": 71,
            "all_additive_query_keys_fingerprint": global_fp,
            "selected_query_keys": [
                [f"T{index * 40 + n:05d}", "2022-01-03", "2022-03-18"]
                for n in range(count)
            ],
        }
        path = tmp_path / f"original_{index:03d}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[index] = path

    def read_bound(s, i, fp):
        assert s is settings and fp == bulk.shards.FROZEN_PRIOR_PLAN
        return {"plan_fingerprint": f"p{i}"}, paths[i], {"shard_index": i}

    monkeypatch.setattr(bulk.shards, "_read_bound", read_bound)
    metrics = {"prior_calls": 0, "loader_calls": 0, "source_calls": [],
               "active": 0, "peak": 0, "preparer_calls": [], "quote_calls": 0}
    lock = threading.Lock()
    complete_sources = set()
    quote_complete = 2725

    def prior(s):
        assert s is settings
        metrics["prior_calls"] += 1
        return ({"plan_fingerprint": bulk.shards.FROZEN_PRIOR_PLAN},
                {f"old-{n}" for n in range(36)},
                {("ORIGINAL", "2022-01-03", "2022-03-18")})

    def loader(*a, **kw):
        metrics["loader_calls"] += 1
        return ("accepted", {"source_integrity_fingerprint": "synthetic"})

    def prepare(s, *, shard_index, duckdb_threads, loader, verified_prior, progress):
        assert s is settings and duckdb_threads == 4
        assert verified_prior[0]["plan_fingerprint"] == bulk.shards.FROZEN_PRIOR_PLAN
        assert shard_index >= 26
        metrics["preparer_calls"].append(shard_index)
        if not metrics.get("loaded"):
            assert loader()[0] == "accepted"
            metrics["loaded"] = True
        return (
            {"plan_fingerprint": f"p{shard_index}",
             "shared_chain_requests": len(json.loads(paths[shard_index].read_text())["selected_query_keys"]),
             "shard_index": shard_index},
            paths[shard_index],
            {"shard_index": shard_index, "source_sha256": f"sha{shard_index}",
             "plan_fingerprint": f"p{shard_index}"},
            "REUSED_IMMUTABLE_ADDITIVE_SHARD",
        )

    def source(s, plan, path, **kw):
        assert s is settings and kw["classify_no_data"] is True
        index = plan["shard_index"]
        count = plan["shared_chain_requests"]
        with lock:
            metrics["source_calls"].append(index)
            metrics["active"] += 1
            metrics["peak"] = max(metrics["peak"], metrics["active"])
        try:
            time.sleep(0.003)
            if index == fail_shard:
                raise TimeoutError("synthetic original request uncertain")
            new = 0 if index in complete_sources else count
            complete_sources.add(index)
            return {
                "status": "COMPLETE",
                "pending": 0, "completed_chains": count, "proven_exact_query_gaps": 0,
                "new_provider_attempts_this_invocation": new,
                "observed_provider_credits_this_invocation": new,
                "last_observed_credits_remaining": 240 if low_remaining else 9000 - index * 40,
                "report_fingerprint": f"source-{index}",
            }
        finally:
            with lock:
                metrics["active"] -= 1

    plan = {
        "plan_fingerprint": "b" * 64,
        "source_gaps": [1, 2], "selected_candidate_memberships": 6500,
        "unique_exact_quote_series": 6000,
    }

    def planner(s, *, last_shard_inclusive):
        assert s is settings and last_shard_inclusive == 70
        return plan

    def quotes(s, p, *, max_new_requests, max_observed_credits,
               workers, authorize, paid, private, token, progress):
        nonlocal quote_complete
        assert s is settings and p == plan and workers == 24
        assert authorize and paid and private and token == "synthetic"
        assert max_new_requests <= 3000 and max_observed_credits <= 3500
        metrics["quote_calls"] += 1
        new = min(max_new_requests, max_observed_credits, 6000-quote_complete)
        quote_complete += new
        progress({"stage": "BOUNDED_QUOTE_BATCH", "configured_workers": workers, "new_attempts": new})
        return {
            "status": "COMPLETE_SOURCE_ONLY" if quote_complete == 6000 else "PARTIAL_BUDGET_OR_CREDIT_FLOOR",
            "plan_fingerprint": p["plan_fingerprint"], "report_fingerprint": f"quote-{metrics['quote_calls']}",
            "unique_exact_quote_series": 6000, "complete_source_series": quote_complete,
            "exact_source_gaps": 0, "pending": 6000-quote_complete,
            "new_provider_attempts": new, "observed_credits_this_invocation": new,
            "last_observed_provider_remaining": 7000-metrics["quote_calls"]*new,
            "verified_and_new_raw_body_bytes": 55_000_000,
        }

    def audit(s, *, last_shard_inclusive):
        assert s is settings and last_shard_inclusive == 70
        metrics["audit_calls"] = metrics.get("audit_calls", 0) + 1
        return {
            "status": "COMPLETE_SOURCE_ONLY",
            "frozen_plan_fingerprint": plan["plan_fingerprint"],
            "unique_exact_quote_series": 6000,
            "complete_exact_histories": 6000,
            "exact_quote_no_data_gaps": 0, "pending_exact_histories": 0,
            "provider_requests_this_audit": 0,
            "audit_fingerprint": "synthetic-audit",
            "total_observed_eod_rows": 300000,
            "rows_with_positive_reported_volume": 100000,
            "rows_with_zero_reported_volume": 200000,
            "histories_with_no_positive_reported_volume": 400,
        }

    kwargs = dict(prior_reader=prior, preparer=prepare, loader=loader,
                  source_runner=source, plan_builder=planner, quote_runner=quotes,
                  coverage_auditor=audit)
    return settings, kwargs, metrics, complete_sources


def _run(s, kw, **extra):
    return bulk.run_complete_2022_bulk(
        s, authorize=True, paid=True, private=True, token="synthetic", **kw, **extra
    )


def test_full_single_command_adapts_network_workers_and_reuses_full_quote_cache(tmp_path, monkeypatch):
    s, kw, m, complete = _rig(tmp_path, monkeypatch)
    progress = []
    out = _run(s, kw, progress=progress.append)
    assert out["status"] == "COMPLETE_FROZEN_2022_SOURCE_AND_QUOTE_CORPUS"
    assert out["source_range_total"] == "0..70"
    assert out["frozen_global_chain_keys"] == 2812
    assert out["source_shards_completed_this_run"] == 45
    assert out["new_chain_requests"] == 1772
    assert out["new_quote_requests"] == 3275
    assert out["observed_total_credits"] == 5047
    assert out["complete_exact_histories_including_reused"] == 6000
    assert out["pending_quote_histories"] == 0
    assert out["terminal_local_audit_fingerprint"] == "synthetic-audit"
    assert out["terminal_observed_eod_rows"] == 300000
    assert out["original_paid_receipts_replayed"] == 0
    assert m["prior_calls"] == m["loader_calls"] == 1
    assert m["peak"] >= 8
    assert m["quote_calls"] == 2
    assert len(complete) == 45
    waves = [x for x in progress if x["stage"] == "CHAIN_WAVE_COMPLETE"]
    assert len(waves) >= 2
    assert waves[0]["active_network_workers"] == 8
    assert max(x["active_network_workers"] for x in waves) > 8
    assert [x["quote_event"]["stage"] for x in progress if x["stage"] == "QUOTES"] == [
        "BOUNDED_QUOTE_BATCH", "BOUNDED_QUOTE_BATCH"
    ]
    # Completed original sources and quote series are not billed again on a resume.
    resumed = _run(s, kw)
    assert resumed["new_chain_requests"] == resumed["new_quote_requests"] == 0
    assert resumed["status"] == "COMPLETE_FROZEN_2022_SOURCE_AND_QUOTE_CORPUS"
    assert m["quote_calls"] == 3  # read-only original quote census, zero HTTP GET
    assert m["audit_calls"] == 2  # local only; no provider charge


def test_budgeted_source_stop_does_not_plan_or_call_quotes(tmp_path, monkeypatch):
    s, kw, m, complete = _rig(tmp_path, monkeypatch)
    def unexpected(*a, **k):
        raise AssertionError("quote phase cannot start before all source shards terminal")
    kw["plan_builder"] = unexpected
    kw["quote_runner"] = unexpected
    result = _run(s, kw, max_total_new_chain_requests=320,
                  max_total_observed_credits=320)
    assert result["status"] == "PARTIAL_CHAIN_BUDGET_OR_PROVIDER_FLOOR_NO_QUOTES"
    assert result["source_shards_completed_this_run"] == 8
    assert result["last_completed_shard"] == 33
    assert result["new_quote_requests"] == 0
    assert len(complete) == 8


def test_uncertain_original_preserves_wave_and_blocks_future_dispatch(tmp_path, monkeypatch):
    s, kw, m, complete = _rig(tmp_path, monkeypatch, fail_shard=29)
    def unexpected(*a, **k):
        raise AssertionError("failed source phase cannot access quotes")
    kw["plan_builder"] = unexpected
    kw["quote_runner"] = unexpected
    with pytest.raises(CandidateChainCacheError, match="in-flight receipts retained"):
        _run(s, kw)
    assert set(m["source_calls"]) == set(range(26, 34))
    assert 29 not in complete
    assert m["quote_calls"] == 0


def test_credit_floor_and_immutable_quote_plan(tmp_path, monkeypatch):
    s, kw, m, complete = _rig(tmp_path, monkeypatch, low_remaining=True)
    kw["plan_builder"] = lambda *a, **k: pytest.fail("credit floor before quote plan")
    out = _run(s, kw)
    assert out["status"] == "PARTIAL_CHAIN_BUDGET_OR_PROVIDER_FLOOR_NO_QUOTES"
    assert out["last_provider_remaining"] == 240
    s2, kw2, m2, complete2 = _rig(tmp_path / "other", monkeypatch)
    first = _run(s2, kw2)
    assert first["status"] == "COMPLETE_FROZEN_2022_SOURCE_AND_QUOTE_CORPUS"
    changed = dict(kw2["plan_builder"](s2, last_shard_inclusive=70))
    changed["selected_candidate_memberships"] += 1
    kw2["plan_builder"] = lambda *a, **k: changed
    kw2["quote_runner"] = lambda *a, **k: pytest.fail("changed plan cannot call provider")
    with pytest.raises(CandidateChainCacheError, match="previously frozen"):
        _run(s2, kw2)


def test_authorization_and_configuration_fail_before_source(tmp_path, monkeypatch):
    s, kw, m, complete = _rig(tmp_path, monkeypatch)
    for extra in (
        {"authorize": False}, {"token": ""}, {"max_total_new_chain_requests": 1801},
        {"max_chain_workers": 25}, {"initial_chain_workers": 2},
    ):
        data=dict(kw,authorize=True,paid=True,private=True,token="synthetic")
        data.update(extra)
        with pytest.raises(CandidateChainCacheError):
            bulk.run_complete_2022_bulk(s, **data)
    assert m["prior_calls"] == 0
    assert m["loader_calls"] == 0
    assert m["source_calls"] == []
