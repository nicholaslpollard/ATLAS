from __future__ import annotations

"""Offline tests: full 2022 immutable original source and bulk orchestration."""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import packages.data.marketdata_2022_full_bulk_v1 as bulk
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


ET = ZoneInfo("America/New_York")


def _settings(tmp_path):
    return SimpleNamespace(project_root=tmp_path, resolved_path=lambda s: tmp_path / s)


def _plans(tmp_path, first_pending=range(26, 32)):
    return [
        (i, {"requests": [{"request_identity": f"exact-{i}-{j}"} for j in range(2)],
             "plan_fingerprint": f"plan-{i}", "shared_chain_requests": 2},
         tmp_path / f"source-{i}.json", 2)
        for i in range(26, 71)
    ]


def _chain(plan, pending, *, charges=0, remaining=None):
    total = len(plan["requests"])
    return {
        "completed_chains": total - pending,
        "proven_exact_query_gaps": 0,
        "pending": pending,
        "new_provider_attempts_this_invocation": total - pending if charges else 0,
        "observed_provider_credits_this_invocation": charges,
        "last_observed_credits_remaining": remaining,
    }


def _full_plan(unique=5000):
    return {"plan_fingerprint": "a" * 64, "unique_exact_quote_series": unique,
            "selected_candidate_memberships": unique + 100}


def _fake_quote(plan, calls, *, complete):
    return {
        "plan_fingerprint": plan["plan_fingerprint"],
        "unique_exact_quote_series": plan["unique_exact_quote_series"],
        "complete_source_series": complete,
        "exact_source_gaps": 0,
        "pending": plan["unique_exact_quote_series"] - complete,
        "new_provider_attempts": calls,
        "observed_credits_this_invocation": calls,
        "last_observed_provider_remaining": 7000 - (complete - 2725),
        "verified_and_new_raw_body_bytes": complete * 1000,
        "status": "COMPLETE_SOURCE_ONLY" if complete == plan["unique_exact_quote_series"]
                  else "PARTIAL_BUDGET_OR_CREDIT_FLOOR",
    }


def test_whole_2022_parallel_original_chains_then_adaptive_quote_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    lock = threading.Lock()
    gate = threading.Barrier(4, timeout=5)
    active = peak = 0
    seen = []
    pending = set(range(26, 32))
    quote_workers = []
    total_complete = 2725
    plan = _full_plan(unique=5000)
    events = []

    def chain_runner(settings, source_plan, source_path, **kw):
        nonlocal active, peak
        i = int(source_plan["plan_fingerprint"].split("-")[-1])
        if not kw:
            return _chain(source_plan, 2 if i in pending else 0)
        with lock:
            active += 1
            peak = max(peak, active)
            seen.append(i)
        try:
            if i in range(26, 30):
                gate.wait()
            pending.discard(i)
            return _chain(source_plan, 0, charges=2, remaining=8000 - 2 * len(seen))
        finally:
            with lock:
                active -= 1

    def quote_runner(settings, frozen, **kw):
        nonlocal total_complete
        quote_workers.append(kw["workers"])
        n = min(kw["max_new_requests"], frozen["unique_exact_quote_series"] - total_complete)
        total_complete += n
        kw["progress"]({"stage": "BOUNDED_QUOTE_BATCH", "new_gets_per_second": 3.0})
        return _fake_quote(frozen, n, complete=total_complete)

    result = bulk.run_full_bulk(
        _settings(tmp_path), authorize=True, paid=True, private=True,
        token="synthetic", progress=events.append, max_credit_windows=1,
        prepare_sources=lambda *_a, **_kw: _plans(tmp_path),
        chain_runner=chain_runner, plan_builder=lambda *_: plan,
        quote_runner=quote_runner,
    )
    assert result["status"] == "COMPLETE_SOURCE_ONLY"
    assert peak == 4
    assert sorted(seen) == list(range(26, 32))
    assert result["source_shards_complete_26_to_70"] == 45
    assert result["source_shards_pending"] == 0
    assert result["new_chain_gets"] == 12
    assert result["new_quote_gets"] == 2275
    assert result["observed_total_credits"] == 2287
    assert result["complete_exact_quote_histories"] == 5000
    assert result["pending_exact_quote_histories"] == 0
    assert quote_workers[0] == 16 and all(8 <= x <= 24 for x in quote_workers)
    assert quote_workers[1] == 20
    assert [e["workers"] for e in events if e["stage"] == "SOURCE_PARALLEL_WAVE"] == [4, 2]
    assert not (tmp_path / bulk.REPORT_REL / "acquisition.lock").exists()
    assert json.loads((tmp_path / bulk.REPORT_REL / "latest.json").read_text())["status"] == "COMPLETE_SOURCE_ONLY"


def test_existing_chains_and_quotes_are_not_redownloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    plan = _full_plan(unique=2725)
    seen = []

    def chain(settings, p, path, **kw):
        assert not kw
        return _chain(p, 0)

    def quotes(settings, p, **kw):
        seen.append(kw["max_new_requests"])
        return _fake_quote(p, 0, complete=2725)

    result = bulk.run_full_bulk(
        _settings(tmp_path), authorize=True, paid=True, private=True,
        token="synthetic", max_credit_windows=1,
        prepare_sources=lambda *_a, **_kw: _plans(tmp_path),
        chain_runner=chain, plan_builder=lambda *_: plan,
        quote_runner=quotes,
    )
    assert result["status"] == "COMPLETE_SOURCE_ONLY"
    assert result["new_chain_gets"] == result["new_quote_gets"] == 0
    assert result["observed_total_credits"] == 0
    assert seen == [1024]


def test_global_credit_target_prevents_new_paid_chain_wave_and_quote(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    seen = []
    result = bulk.run_full_bulk(
        _settings(tmp_path), authorize=True, paid=True, private=True,
        token="synthetic", max_total_observed_credits=1,
        max_credit_windows=1,
        prepare_sources=lambda *_a, **_kw: _plans(tmp_path),
        chain_runner=lambda s,p,path,**kw: (_chain(p,2) if not kw
                         else pytest.fail("no provider reads with insufficient combined budget")),
        plan_builder=lambda *_: pytest.fail("no quote plan from partial chain"),
    )
    assert result["status"] == "PARTIAL_BUDGET_OR_PROVIDER_FLOOR"
    assert result["new_chain_gets"] == result["new_quote_gets"] == 0
    assert (tmp_path / bulk.REPORT_REL / "latest.json").exists()


def test_uncertain_chain_worker_joins_wave_and_never_starts_quote(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    attempted = []
    finished = []

    def chain(s,p,path,**kw):
        i = int(p["plan_fingerprint"].split("-")[-1])
        if not kw:
            return _chain(p,2 if i in range(26,30) else 0)
        attempted.append(i)
        if i == 26:
            raise CandidateChainCacheError("synthetic uncertain original")
        finished.append(i)
        return _chain(p, 0, charges=2, remaining=8000)

    with pytest.raises(CandidateChainCacheError, match="uncertain/quarantined"):
        bulk.run_full_bulk(
            _settings(tmp_path), authorize=True, paid=True, private=True,
            token="synthetic", max_credit_windows=1,
            prepare_sources=lambda *_a, **_kw: _plans(tmp_path),
            chain_runner=chain,
            plan_builder=lambda *_: pytest.fail("quote plan cannot start"),
        )
    assert sorted(attempted) == [26,27,28,29]
    assert sorted(finished) == [27,28,29]
    state = json.loads((tmp_path / bulk.REPORT_REL / "latest.json").read_text())
    assert state["status"] == "STOPPED_ORIGINAL_EVIDENCE_REVIEW_REQUIRED"
    assert state["failure_class"] == "CandidateChainCacheError"
    assert not (tmp_path / bulk.REPORT_REL / "acquisition.lock").exists()


def test_daily_reset_wait_does_not_issue_probe_or_replay_receipts(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    plan = _full_plan(unique=2800)
    complete = 2725
    calls = []
    clock = [datetime(2026,9,27,15,0,tzinfo=ET)]
    sleeps = []

    def advance(seconds):
        sleeps.append(seconds)
        clock[0] = bulk._next_reset(clock[0]) + timedelta(seconds=1)

    def quote(s,p,**kw):
        nonlocal complete
        calls.append(kw["max_new_requests"])
        n = min(kw["max_new_requests"], p["unique_exact_quote_series"]-complete)
        complete += n
        return {
            **_fake_quote(p, n, complete=complete),
            "last_observed_provider_remaining": 210 if len(calls)==1 else 9800,
        }

    # Initial one benign source wave shows provider headroom just above floor,
    # then full quoted histories begin with a low remaining header. The
    # orchestrator must wait to 9:31:30 ET before any further GET.
    result = bulk.run_full_bulk(
        _settings(tmp_path), authorize=True, paid=True, private=True,
        token="synthetic", max_credit_windows=2,
        prepare_sources=lambda *_a, **_kw: _plans(tmp_path),
        chain_runner=lambda s,p,path,**kw: _chain(p,0),
        plan_builder=lambda *_: plan, quote_runner=quote,
        clock=lambda: clock[0], sleeper=advance,
    )
    assert result["status"] == "COMPLETE_SOURCE_ONLY"
    assert result["new_quote_gets"] == 75
    assert result["credit_windows_started"] == 1  # no wait after already completing


def test_provider_credit_floor_wait_only_when_work_remains(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    plan = _full_plan(unique=4000)
    calls = []
    clock = [datetime(2026,9,27,15,0,tzinfo=ET)]
    sleeps = []

    def advance(seconds):
        sleeps.append(seconds)
        clock[0] = bulk._next_reset(clock[0]) + timedelta(seconds=1)

    def quote(s,p,**kw):
        calls.append(kw["max_new_requests"])
        complete = 2725 + min(len(calls), 2) * 1024
        complete = min(4000, complete)
        return {
            **_fake_quote(p, 1024 if len(calls)==1 else 251, complete=complete),
            "last_observed_provider_remaining": 210 if len(calls)==1 else 9800,
        }

    state = bulk.run_full_bulk(
        _settings(tmp_path), authorize=True, paid=True, private=True,
        token="synthetic", max_credit_windows=2,
        prepare_sources=lambda *_a, **_kw: _plans(tmp_path),
        chain_runner=lambda s,p,path,**kw: _chain(p,0),
        plan_builder=lambda *_: plan, quote_runner=quote,
        clock=lambda: clock[0], sleeper=advance,
    )
    assert state["status"] == "COMPLETE_SOURCE_ONLY"
    assert state["credit_windows_started"] == 2
    assert len(sleeps) == 1
    assert clock[0].hour == 9 and clock[0].minute == 31
    assert calls == [1024, 1024]


def test_explicit_paid_permission_and_exclusive_lock_before_any_source_work(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    bad = lambda *_a, **_kw: pytest.fail("source must not load")
    with pytest.raises(CandidateChainCacheError, match="confirmations"):
        bulk.run_full_bulk(
            _settings(tmp_path), authorize=False, paid=True, private=True,
            token="synthetic", prepare_sources=bad,
        )
    path = tmp_path / bulk.REPORT_REL / "acquisition.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"unresolved":true}\n')
    with pytest.raises(CandidateChainCacheError, match="owns the lock"):
        bulk.run_full_bulk(
            _settings(tmp_path), authorize=True, paid=True, private=True,
            token="synthetic", prepare_sources=bad,
        )
    assert path.read_text() == '{"unresolved":true}\n'


@pytest.mark.parametrize("timestamp,expected", [
    (datetime(2026,9,27,8,0,tzinfo=ET), (2026,9,27)),
    (datetime(2026,9,27,15,0,tzinfo=ET), (2026,9,28)),
    (datetime(2026,11,1,15,0,tzinfo=ET), (2026,11,2)),
])
def test_next_daily_reset_uses_eastern_not_utc_or_midnight(timestamp, expected):
    due = bulk._next_reset(timestamp)
    assert (due.year,due.month,due.day)==expected
    assert (due.hour,due.minute,due.second)==(9,31,30)


def test_prepare_all_origins_once_and_reject_collision(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk.shards, "_prior",
                        lambda s: ({"plan_fingerprint": bulk.shards.FROZEN_PRIOR_PLAN},
                                   {"id"+str(i) for i in range(36)},
                                   {("T0","2022-01-01","2022-02-18")}))
    source_loads = []
    seen = []
    fp = "c" * 64
    def make(i):
        size = 12 if i==70 else 40
        source_path = tmp_path / f"source-{i}.json"
        source_path.write_text(json.dumps({
            "shard_index":i, "total_additive_shards":71,
            "all_additive_query_keys_fingerprint":fp,
            "selected_query_keys":[[f"T{i:02d}-{j:02d}", "2022-01-03","2022-02-18"]
                                   for j in range(size)],
        }))
        plan = {"plan_fingerprint":str(i), "requests":[{}]*size}
        binding = {"plan_fingerprint":str(i), "shared_chains":size}
        return plan,source_path,binding
    monkeypatch.setattr(bulk.shards, "_read_bound",lambda s,i,prior: make(i))
    monkeypatch.setattr(bulk.shards, "_binding_path",
                        lambda s,i: tmp_path/f"bound-{i}.json")
    for i in range(26):
        (tmp_path/f"bound-{i}.json").write_text("{}")
    def prepare(s,*,shard_index,loader,verified_prior,**kw):
        loader()
        seen.append(shard_index)
        return (*make(shard_index),"NEW")
    monkeypatch.setattr(bulk.shards,"prepare_additive_shard",prepare)
    loader=lambda:source_loads.append(1) or ("source","evidence")
    a=bulk._source_plans(_settings(tmp_path),duckdb_threads=4,progress=lambda *_:None,loader=loader)
    assert len(a)==45 and sum(x[-1] for x in a)==1772
    assert seen==list(range(26,71)) and len(source_loads)==1



def test_adaptive_quote_workers_ramp_reduce_and_hold_at_caps():
    f = bulk._adapt_quote_workers
    assert f(16, 0, 2.8, 1000) == 20
    assert f(20, 2.8, 2.9, 1000) == 24
    assert f(24, 2.8, 3.0, 1000) == 24
    assert f(24, 3.0, 2.2, 1000) == 20
    assert f(8, 3.0, 2.2, 1000) == 8
    assert f(16, 3.0, 3.0, 127) == 16
    assert f(16, 3.0, 2.5, 1000) == 16



def test_adaptive_source_workers_use_measured_gets_per_second():
    f = bulk._adapt_chain_workers
    assert f(4, 0.0, 1.2) == 6
    assert f(6, 1.2, 2.0) == 8
    assert f(8, 2.0, 2.4) == 8
    assert f(8, 2.4, 1.6) == 6
    assert f(4, 2.4, 2.0) == 4
    assert f(2, 2.0, 1.0) == 2
