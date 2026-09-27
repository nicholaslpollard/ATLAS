from __future__ import annotations

"""Zero-provider tests of original receipt barriers in the coordinated campaign."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_2022_coordinated_chain_quote_v1 as c
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _settings(tmp_path):
    return SimpleNamespace(resolved_path=lambda p: tmp_path / p)


def _source(start=16, count=10, *, status="COMPLETE_CAMPAIGN_RANGE",
            pending_index=None, credits=375, remaining=7900):
    rows = [
        {"shard_index": i, "pending": 1 if i == pending_index else 0}
        for i in range(start, start + count)
    ]
    return {
        "status": status, "shard_reports": rows,
        "new_provider_attempts": 400, "observed_credits": credits,
        "last_observed_provider_remaining": remaining,
        "campaign_fingerprint": "a" * 64,
    }


def _plan():
    return {
        "plan_fingerprint": "b" * 64,
        "source_gaps": [1, 2],
        "selected_candidate_memberships": 2550,
        "unique_exact_quote_series": 2300,
    }


def _quote(plan, *, status="COMPLETE_SOURCE_ONLY", pending=0):
    return {
        "status": status, "plan_fingerprint": plan["plan_fingerprint"],
        "report_fingerprint": "c" * 64,
        "unique_exact_quote_series": plan["unique_exact_quote_series"],
        "complete_source_series": plan["unique_exact_quote_series"] - pending,
        "exact_source_gaps": 0,
        "pending": pending, "new_provider_attempts": 600,
        "observed_credits_this_invocation": 599,
        "last_observed_provider_remaining": 7300,
        "verified_and_new_raw_body_bytes": 25_000_000,
    }


def _run(tmp_path, monkeypatch, *, chain=None, plan=None, quote=None, **kw):
    monkeypatch.setattr(c, "_require_external", lambda s: None)
    chain = chain or _source()
    plan = plan or _plan()
    return c.run_coordinated_batch(
        _settings(tmp_path),
        authorize=True, paid=True, private=True, token="synthetic",
        chain_runner=lambda *a, **k: chain,
        plan_builder=lambda *a, **k: plan,
        quote_runner=lambda *a, **k: quote or _quote(plan),
        **kw,
    )


def test_full_source_then_only_new_quote_calls_and_combined_credit_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "_require_external", lambda *_: None)
    s = _settings(tmp_path)
    calls = []
    plan = _plan()

    def chain_runner(settings, **kw):
        calls.append(("chain", kw))
        return _source()

    def planner(settings, **kw):
        calls.append(("plan", kw))
        return plan

    def quote_runner(settings, source_plan, **kw):
        calls.append(("quote", kw))
        assert source_plan == plan
        return _quote(plan)

    progress = []
    result = c.run_coordinated_batch(
        s, authorize=True, paid=True, private=True, token="synthetic",
        chain_runner=chain_runner, plan_builder=planner,
        quote_runner=quote_runner, progress=progress.append,
    )
    assert result["status"] == "COMPLETE_CHAIN_AND_QUOTE_RANGE"
    assert result["new_chain_requests"] == 400
    assert result["new_quote_requests"] == 600
    assert result["observed_chain_credits"] == 375
    assert result["observed_quote_credits"] == 599
    assert result["observed_total_credits"] == 974
    assert result["unique_exact_histories_including_reused"] == 2300
    assert result["original_paid_receipts_replayed"] == 0
    assert [x[0] for x in calls] == ["chain", "plan", "quote"]
    assert calls[0][1]["classify_no_data"] is True
    assert calls[0][1]["max_observed_credits"] == 500
    assert calls[-1][1]["workers"] == 16
    assert calls[-1][1]["max_observed_credits"] == 3125
    assert [x["stage"] for x in progress if x["stage"] != "CHAIN"] == [
        "COORDINATED_PREFLIGHT", "SOURCE_RANGE_FINISHED", "QUOTE_PLAN_VERIFIED",
    ]
    assert (tmp_path / c.PLAN_REL / "through_shard_025.json").is_file()


def test_partial_chain_never_plans_or_calls_quote_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "_require_external", lambda *_: None)
    calls = []
    s = _settings(tmp_path)
    partial = _source(status="PARTIAL_CAMPAIGN_BUDGET", pending_index=24)

    def bad(*args, **kwargs):
        calls.append("unexpected")
        raise AssertionError("no quote planner/provider after partial source")

    out = c.run_coordinated_batch(
        s, authorize=True, paid=True, private=True, token="synthetic",
        chain_runner=lambda *a, **kw: partial,
        plan_builder=bad, quote_runner=bad,
    )
    assert out["status"] == "SOURCE_RANGE_INCOMPLETE_NO_QUOTE_REQUESTS"
    assert out["new_quote_requests"] == 0
    assert calls == []
    assert not (tmp_path / c.PLAN_REL / "through_shard_025.json").exists()


def test_missing_paid_confirmations_or_token_stops_before_source(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "_require_external", lambda *_: None)
    settings = _settings(tmp_path)

    def bad(*args, **kwargs):
        raise AssertionError("provider preflight must abort before source")

    for kw in (
        {"authorize": False, "paid": True, "private": True, "token": "ok"},
        {"authorize": True, "paid": True, "private": True, "token": ""},
    ):
        with pytest.raises(CandidateChainCacheError, match="confirmations"):
            c.run_coordinated_batch(settings, chain_runner=bad, **kw)


def test_source_provider_credit_floor_stops_quote_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "_require_external", lambda *_: None)

    def bad(*args, **kwargs):
        raise AssertionError("quote stage must not run after global provider floor")

    out = c.run_coordinated_batch(
        _settings(tmp_path),
        authorize=True, paid=True, private=True, token="synthetic",
        chain_runner=lambda *a, **k: _source(remaining=210),
        plan_builder=bad, quote_runner=bad,
    )
    assert out["status"] == "SOURCE_COMPLETE_QUOTE_CREDIT_GATE"
    assert out["new_quote_requests"] == 0


def test_frozen_plan_mismatch_refuses_paid_quote_on_restart(tmp_path, monkeypatch):
    first = _run(tmp_path, monkeypatch)
    assert first["status"] == "COMPLETE_CHAIN_AND_QUOTE_RANGE"
    tampered = _plan()
    tampered["unique_exact_quote_series"] += 1

    def bad(*args, **kwargs):
        raise AssertionError("must not request quotes under mutated frozen plan")

    monkeypatch.setattr(c, "_require_external", lambda *_: None)
    with pytest.raises(CandidateChainCacheError, match="previously frozen"):
        c.run_coordinated_batch(
            _settings(tmp_path), authorize=True, paid=True, private=True,
            token="synthetic", chain_runner=lambda *a, **kw: _source(),
            plan_builder=lambda *a, **kw: tampered, quote_runner=bad,
        )


def test_quote_budget_partial_is_visible_and_request_limits_checked(tmp_path, monkeypatch):
    p = _plan()
    partial = _quote(p, status="PARTIAL_BUDGET_OR_CREDIT_FLOOR", pending=300)
    out = _run(tmp_path, monkeypatch, quote=partial)
    assert out["status"] == "SOURCE_COMPLETE_QUOTE_PARTIAL"
    assert out["pending_quote_histories"] == 300
    assert out["complete_exact_histories_including_reused"] == 2000
    with pytest.raises(CandidateChainCacheError, match="source range"):
        _run(tmp_path, monkeypatch, start_shard=70, shard_count=10)
    with pytest.raises(CandidateChainCacheError, match="request limits"):
        _run(tmp_path, monkeypatch, max_new_chain_requests=401)
    with pytest.raises(CandidateChainCacheError, match="worker"):
        _run(tmp_path, monkeypatch, workers=25)
