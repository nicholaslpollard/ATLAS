from __future__ import annotations

"""Synthetic original-source test: future EOD never chooses a contract or implies fill."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_2022_ranked_eod_readiness_v1 as m
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    POLICY_VERSION, WIDE_POLICY, PLAN_REL,
)
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data.marketdata_2022_selected_quote_campaign_v1 import CONTRACT as QUOTE_CONTRACT


def _fixture(tmp_path, monkeypatch):
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    sources = []
    source_plans = []
    for i in range(71):
        source_plans.append({"shard_index": i, "source_sha256": f"sha{i}",
                             "chain_plan_fingerprint": f"plan{i}"})
        source = {"year": 2022, "shard_index": i, "rows": []}
        if i == 0:
            for oid, signal, decision in (
                ("one", "2022-03-01", "2022-03-02T14:35:00+00:00"),
                ("two", "2022-03-07", "2022-03-08T14:35:00+00:00"),
            ):
                source["rows"].append({
                    "opportunity_id": oid, "signal_session": signal,
                    "snapshot_date": signal, "decision_at_utc": decision,
                    "expiration": "2022-12-16", "ticker": "TEST", "side": "call",
                    "raw_underlying_price": "10.0",
                })
        path = tmp_path / f"source_{i}.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        sources.append(path)

    symbol = "TEST221216C00010000"
    tickets = [{
        "request_identity": _fingerprint({"id": i}),
        "option_symbol": symbol if i == 0 else f"TEST{i:04d}221216C00010000",
        "to_exclusive": "2022-12-17", "source_shard_memberships": [],
    } for i in range(6398)]
    tickets[0]["source_shard_memberships"] = [
        {"rank": 0, "shard_index": 0, "opportunity_id": oid,
         "raw_underlying_open": "10.0"}
        for oid in ("one", "two")
    ]
    # A different structural rank must never replace rank 0 based on future EOD rows.
    tickets[1]["source_shard_memberships"] = [
        {"rank": 1, "shard_index": 0, "opportunity_id": "one",
         "raw_underlying_open": "10.0"}
    ]
    plan = {
        "contract": QUOTE_CONTRACT, "last_shard_inclusive": 70,
        "selection_policy": WIDE_POLICY, "provider_reads_in_planning": 0,
        "unique_exact_quote_series": 6398, "requests": tickets,
        "source_plans": source_plans,
        "broad_acquisition_envelope_v2": {
            "policy_version": POLICY_VERSION, "alternate_expiration_sources_acquired": False,
        },
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    monkeypatch.setattr(m, "EXPECTED_PLAN", plan["plan_fingerprint"])
    path = tmp_path / PLAN_REL / "through_shard_070.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan), encoding="utf-8")

    def prior(s):
        assert s is settings
        return ({"plan_fingerprint": "original"}, set(), set())

    def bound(s, i, prior_fp):
        assert s is settings and prior_fp == "original"
        return ({"plan_fingerprint": f"plan{i}"}, sources[i],
                {"source_sha256": f"sha{i}"})

    def quote(s, ticket):
        assert s is settings and ticket is tickets[0]
        return {"status": "COMPLETE_SOURCE_ONLY", "safe_summary": {"observed_rows": 4}}

    def timestamp(year, month, day):
        return int(datetime(year, month, day, 21, tzinfo=UTC).timestamp())

    def raw(s, ticket):
        assert s is settings and ticket is tickets[0]
        # March 2 EOD is future relative to the original 09:35 decision and
        # MUST be excluded as an entry observation.
        return json.dumps({
            "s": "ok", "optionSymbol": [symbol]*4,
            "updated": [timestamp(2022,3,2), timestamp(2022,3,3),
                        timestamp(2022,3,4), timestamp(2022,3,7)],
            "bid": [1.0, 0.0, 1.1, 1.2], "ask": [1.2, 1.2, 1.3, 1.4],
            "volume": [20, 0, 0, 3],
        }).encode()

    kwargs = dict(expected_plan=plan["plan_fingerprint"], prior_reader=prior,
                  bound_reader=bound, quote_reader=quote, raw_reader=raw)
    return settings, kwargs, path


def test_post_decision_context_no_same_day_lookahead_and_zero_provider_reads(tmp_path, monkeypatch):
    s, kw, _ = _fixture(tmp_path, monkeypatch)
    p = []
    report = m.build_ranked_eod_readiness(s, progress=p.append, **kw)
    assert report["status"] == "RANKED_EOD_SCENARIO_READINESS_ONLY"
    assert report["rank_zero_opportunity_memberships"] == 2
    assert report["unique_rank_zero_quote_histories"] == 1
    assert report["no_later_eod_observation"] == 1
    assert report["later_two_sided_eod_context_only"] == 1
    assert report["later_positive_reported_volume_opportunities"] == 1
    assert report["opportunities_with_two_or_more_later_two_sided_context_dates"] == 1
    assert report["provider_requests"] == 0
    assert report["authority"] == m.AUTHORITY
    one = next(x for x in report["rows"] if x["opportunity_id"] == "one")
    two = next(x for x in report["rows"] if x["opportunity_id"] == "two")
    assert one["first_later_observed_eod_session"] == "2022-03-03"
    assert one["first_later_two_sided_eod_context_session"] == "2022-03-04"
    assert one["first_later_positive_reported_volume_session"] == "2022-03-07"
    assert two["first_later_observed_eod_session"] is None
    assert one["structural_rank"] == two["structural_rank"] == 0
    assert p[-1]["provider_requests"] == 0
    path, action = m.write_ranked_readiness(s, report)
    assert action == "WRITTEN_NEW_READINESS" and path.exists()
    assert m.write_ranked_readiness(s, report)[1] == "REUSED_IDENTICAL_READINESS"
    assert m.build_ranked_eod_readiness(s, **kw) == report


def test_tampered_original_plan_rejected_before_receipts(tmp_path, monkeypatch):
    s, kw, path = _fixture(tmp_path, monkeypatch)
    plan = json.loads(path.read_text())
    plan["unique_exact_quote_series"] += 1
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(CandidateChainCacheError, match="quote-plan identity"):
        m.build_ranked_eod_readiness(s, **kw)


def test_original_quote_missing_fails_closed_without_reacquisition(tmp_path, monkeypatch):
    s, kw, _ = _fixture(tmp_path, monkeypatch)
    kw["quote_reader"] = lambda *a: None
    with pytest.raises(CandidateChainCacheError, match="not complete"):
        m.build_ranked_eod_readiness(s, **kw)


def test_missing_decision_chronology_fails_closed(tmp_path, monkeypatch):
    s, kw, _ = _fixture(tmp_path, monkeypatch)
    original = kw["bound_reader"]
    def modified(settings, i, prior_fp):
        plan, path, binding = original(settings, i, prior_fp)
        if i == 0:
            obj = json.loads(path.read_text())
            obj["rows"][0]["decision_at_utc"] = "2022-03-01T14:35:00+00:00"
            path.write_text(json.dumps(obj), encoding="utf-8")
        return plan, path, binding
    kw["bound_reader"] = modified
    with pytest.raises(CandidateChainCacheError, match="chronology"):
        m.build_ranked_eod_readiness(s, **kw)


def test_existing_different_readiness_never_overwritten(tmp_path, monkeypatch):
    s, kw, _ = _fixture(tmp_path, monkeypatch)
    result = m.build_ranked_eod_readiness(s, **kw)
    path, _ = m.write_ranked_readiness(s, result)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(CandidateChainCacheError, match="differs"):
        m.write_ranked_readiness(s, result)
