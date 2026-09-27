from __future__ import annotations

"""Synthetic-only tests: no real provider data, calls or credentials."""

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_2022_bulk_acquisition_v1 as bulk
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import _read_object


def _settings(tmp_path):
    return SimpleNamespace(resolved_path=lambda p: tmp_path / p)


def _base(tmp_path, monkeypatch):
    root = _settings(tmp_path)
    plan = {
        "contract": "synthetic-existing-broad-quote-plan",
        "unique_exact_quote_series": 2,
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    monkeypatch.setattr(bulk, "BASE_QUOTE_FINGERPRINT", plan["plan_fingerprint"])
    monkeypatch.setattr(bulk, "BASE_QUOTE_SERIES", 2)
    location = tmp_path / bulk.PLAN_REL / "through_shard_025.json"
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(bulk, "_require_external", lambda *_: None)
    return root


def _synthetic_sources(tmp_path):
    output = {}
    for index in (26, 27):
        path = tmp_path / f"source{index}.json"
        path.write_text("{}", encoding="utf-8")
        output[index] = (
            {"requests": [{"request_identity": str(index)}],
             "plan_fingerprint": f"plan{index}",
             "shared_chain_requests": 1},
            path,
            {"shard_index": index, "source_sha256": f"sha{index}"},
        )
    return {
        "manifest_fingerprint": "original-manifest",
        "new_physical_chain_keys": 2,
    }, output


def _quote_plan():
    return {
        "plan_fingerprint": "synthetic-new-broad-plan",
        "source_gaps": [],
        "selected_candidate_memberships": 4,
        "unique_exact_quote_series": 3,
    }


def test_prepare_one_prior_and_one_native_load_and_immutable_source_plan(tmp_path):
    setting = _settings(tmp_path)
    calls = {"prior": 0, "native": 0, "prepare": 0}

    def prior(_s):
        calls["prior"] += 1
        return (
            {"plan_fingerprint": bulk.shards.FROZEN_PRIOR_PLAN},
            {f"orig-{i}" for i in range(36)},
            {("ORIG", str(i), "2022-03-18") for i in range(36)},
        )

    def native(*args, **kwargs):
        calls["native"] += 1
        return ("verified-native", {"source_integrity_fingerprint": "synthetic"})

    def preparer(s, *, shard_index, loader, verified_prior, **_):
        assert s is setting
        assert verified_prior[0]["plan_fingerprint"] == bulk.shards.FROZEN_PRIOR_PLAN
        assert loader() == native()
        calls["prepare"] += 1
        source = {
            "shard_index": shard_index, "total_additive_shards": 71,
            "selected_query_keys": [["ABCD", f"2022-{shard_index:02d}", "2022-12-16"]],
            "all_additive_query_keys_fingerprint": "original-frozen-universe",
            "protected_master_return_rows_read": 0,
        }
        path = tmp_path / f"source-{shard_index}.json"
        if not path.exists():
            path.write_text(json.dumps(source), encoding="utf-8")
        sha = bulk.shards._sha(path)
        plan = {"requests": [{"request_identity": str(shard_index)}],
                "shared_chain_requests": 1,
                "plan_fingerprint": f"plan-{shard_index}"}
        binding = {"source_sha256": sha, "plan_fingerprint": plan["plan_fingerprint"]}
        return plan, path, binding, "REUSED" if path.exists() else "NEW"

    # Native loader only gets called once even though every shard asks for it.
    # The test's explicit native() equality should not independently invoke the
    # loader; use native result as a static expected tuple instead.
    def actual_preparer(s, *, shard_index, loader, verified_prior, **kwargs):
        assert loader() == ("verified-native", {"source_integrity_fingerprint": "synthetic"})
        source = {
            "shard_index": shard_index, "total_additive_shards": 71,
            "selected_query_keys": [["ABCD", f"2022-{shard_index:02d}", "2022-12-16"]],
            "all_additive_query_keys_fingerprint": "original-frozen-universe",
            "protected_master_return_rows_read": 0,
        }
        path = tmp_path / f"source-{shard_index}.json"
        if not path.exists():
            path.write_text(json.dumps(source), encoding="utf-8")
        sha = bulk.shards._sha(path)
        plan = {"requests": [{"request_identity": str(shard_index)}],
                "shared_chain_requests": 1, "plan_fingerprint": f"plan-{shard_index}"}
        return plan, path, {"source_sha256": sha,
                             "plan_fingerprint": plan["plan_fingerprint"]}, "REUSED"

    def fake_batch_builder(s, load, verified_prior, **kwargs):
        assert s is setting
        assert load() == ("verified-native", {"source_integrity_fingerprint": "synthetic"})
        return lambda *_a, **_k: ({}, {"protected_master_return_rows_read": 0})

    first, sources = bulk.prepare_frozen_bulk_sources(
        setting, prior_reader=prior, preparer=actual_preparer, loader=native,
        native_batch_builder=fake_batch_builder,
    )
    assert len(sources) == 45
    assert first["new_physical_chain_keys"] == 45
    assert calls["native"] == 1 and calls["prior"] == 1
    saved = _read_object(tmp_path / bulk.PLAN_REL_PATH)
    assert saved == first
    second, _ = bulk.prepare_frozen_bulk_sources(
        setting, prior_reader=prior, preparer=actual_preparer, loader=native,
        native_batch_builder=fake_batch_builder,
    )
    assert second == first
    assert calls["native"] == 2 and calls["prior"] == 2


def test_parallel_disjoint_sources_then_only_one_new_quote_and_receipts_reused(
    tmp_path, monkeypatch,
):
    settings = _base(tmp_path, monkeypatch)
    manifest, sources = _synthetic_sources(tmp_path)
    states = {26: 0, 27: 0}
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    invoked = []
    quote_plan = _quote_plan()

    def reader(_s, p):
        i = int(p["requests"][0]["request_identity"])
        complete = states[i]
        return {"planned_chain_requests": 1,
                "reused": complete, "no_data_verified": 0,
                "pending": 1-complete}

    def runner(_s, p, source, **kw):
        i = int(p["requests"][0]["request_identity"])
        assert kw["max_total_new_requests"] >= 1
        barrier.wait()
        with lock:
            states[i] = 1
            invoked.append(i)
        return {
            "new_provider_attempts_this_invocation": 1,
            "observed_provider_credits_this_invocation": 1,
            "completed_chains": 1, "proven_exact_query_gaps": 0, "pending": 0,
            "last_observed_credits_remaining": 6500-i,
        }

    quotes = []
    def quote_runner(_s, p, **kw):
        quotes.append(kw["max_new_requests"])
        if kw["max_new_requests"]:
            kw["progress"]({"stage": "SOURCE_ONLY_QUOTE_CENSUS", "pending": 1})
        if kw["max_new_requests"]:
            assert kw["workers"] == 16 and kw["adaptive_workers"] is True
            assert kw["worker_ceiling"] == 24
        return {
            "status": "COMPLETE_SOURCE_ONLY",
            "plan_fingerprint": p["plan_fingerprint"],
            "unique_exact_quote_series": 3,
            "complete_source_series": 3,
            "exact_source_gaps": 0, "pending": 0,
            "new_provider_attempts": 1 if kw["max_new_requests"] else 0,
            "observed_credits_this_invocation": 1 if kw["max_new_requests"] else 0,
            "last_observed_provider_remaining": 6400,
            "verified_and_new_raw_body_bytes": 4000,
        }

    emitted = []
    kw = dict(
        progress=emitted.append,
        source_builder=lambda *_a, **_k: (manifest, sources),
        source_reader=reader, source_runner=runner,
        quote_plan_builder=lambda *_a, **_k: quote_plan,
        quote_runner=quote_runner,
        coverage_auditor=lambda _s, **_kw: {
            "status": "COMPLETE_SOURCE_ONLY",
            "frozen_plan_fingerprint": quote_plan["plan_fingerprint"],
            "unique_exact_quote_series": 3,
            "complete_exact_histories": 3,
            "exact_quote_no_data_gaps": 0,
            "pending_exact_histories": 0,
            "provider_requests_this_audit": 0,
            "audit_fingerprint": "synthetic-audit-sha",
            "total_observed_eod_rows": 11,
            "rows_with_positive_reported_volume": 4,
            "rows_with_zero_reported_volume": 7,
            "histories_with_no_positive_reported_volume": 1,
            "first_observed_session": "2022-01-03",
            "last_observed_session": "2022-03-18",
        },
        source_workers=2, source_worker_ceiling=2,
        authorize=True, paid=True, private=True, token="synthetic",
    )
    result = bulk.run_bulk_2022(settings, **kw)
    assert result["status"] == "COMPLETE_2022_ADDITIVE_CHAINS_AND_QUOTE_SERIES"
    assert sorted(invoked) == [26, 27]
    assert result["new_chain_gets"] == 2
    assert result["new_quote_gets"] == 1
    assert result["total_observed_credits"] == 3
    assert result["post_bulk_offline_coverage_audit_fingerprint"] == "synthetic-audit-sha"
    assert quotes == [3000]
    assert any(x["stage"] == "QUOTES" and x["quote_stage"] == "SOURCE_ONLY_QUOTE_CENSUS"
               for x in emitted)
    assert (tmp_path / bulk.PLAN_REL / "through_shard_070.json").is_file()

    # Exact same immutable sources and quote plan: zero chain calls on resume.
    def bad_runner(*a, **kw):
        pytest.fail("completed original chains must not be requested twice")
    result2 = bulk.run_bulk_2022(
        settings, **{**kw, "source_runner": bad_runner,
                     "quote_runner": lambda _s, p, **k: {
                         **quote_runner(_s, p, **{**k, "max_new_requests": 0}),
                         "new_provider_attempts": 0,
                         "observed_credits_this_invocation": 0,
                     }}
    )
    assert result2["new_chain_gets"] == result2["new_quote_gets"] == 0


def test_partial_source_is_barrier_no_quote_plan_or_provider(tmp_path, monkeypatch):
    settings = _base(tmp_path, monkeypatch)
    manifest, sources = _synthetic_sources(tmp_path)

    def no_quote(*a, **kw):
        pytest.fail("no quote planning or provider GET before source completion")

    result = bulk.run_bulk_2022(
        settings,
        max_new_chain_requests=1, max_new_quote_requests=4,
        source_workers=1, source_worker_ceiling=1,
        source_builder=lambda *_a, **_k: (manifest, sources),
        source_reader=lambda _s, p: {
            "planned_chain_requests": 1, "reused": 0,
            "no_data_verified": 0, "pending": 1,
        },
        source_runner=lambda _s, p, path, **kw: {
            "new_provider_attempts_this_invocation": 1,
            "observed_provider_credits_this_invocation": 1,
            "completed_chains": 0, "proven_exact_query_gaps": 0, "pending": 1,
            "last_observed_credits_remaining": 6000,
        },
        quote_plan_builder=no_quote, quote_runner=no_quote,
        authorize=True, paid=True, private=True, token="synthetic",
    )
    assert result["status"] == "SOURCE_PARTIAL_SAFE_STOP_NO_QUOTES"
    assert result["new_quote_gets"] == 0
    assert result["pending_source_requests"] == 2
    assert not (tmp_path / bulk.PLAN_REL / "through_shard_070.json").exists()


def test_uncertain_parallel_source_drains_started_originals_before_stopping(
    tmp_path, monkeypatch,
):
    settings = _base(tmp_path, monkeypatch)
    manifest, sources = _synthetic_sources(tmp_path)
    barrier = threading.Barrier(2, timeout=5)
    seen = set()

    def run(_s, plan, path, **kwargs):
        i = int(plan["requests"][0]["request_identity"])
        barrier.wait()
        seen.add(i)
        if i == 26:
            raise TimeoutError("original uncertain, durable intent preserved")
        return {"new_provider_attempts_this_invocation": 1,
                "observed_provider_credits_this_invocation": 1,
                "completed_chains": 1, "proven_exact_query_gaps": 0,
                "pending": 0, "last_observed_credits_remaining": 6200}

    with pytest.raises(CandidateChainCacheError, match="all started originals have drained"):
        bulk.run_bulk_2022(
            settings,
            source_workers=2, source_worker_ceiling=2,
            source_builder=lambda *_a, **_k: (manifest, sources),
            source_reader=lambda _s, p: {
                "planned_chain_requests": 1, "reused": 0, "no_data_verified": 0, "pending": 1},
            source_runner=run,
            quote_plan_builder=lambda *_a, **_k: pytest.fail("no quote plan after uncertain"),
            quote_runner=lambda *_a, **_k: pytest.fail("no quote provider after uncertain"),
            authorize=True, paid=True, private=True, token="synthetic",
        )
    assert seen == {26, 27}


def test_credit_floor_and_quote_partial_report_truthfully(tmp_path, monkeypatch):
    settings = _base(tmp_path, monkeypatch)
    manifest, sources = _synthetic_sources(tmp_path)
    def complete(_s, plan):
        return {"planned_chain_requests": 1, "reused": 1, "no_data_verified": 0, "pending": 0}
    plan = _quote_plan()
    def quote(_s, p, **kw):
        assert kw["max_new_requests"] == 0
        return {"status": "PREVIEW_NO_PROVIDER_READS", "plan_fingerprint": p["plan_fingerprint"],
                "unique_exact_quote_series": 3, "complete_source_series": 2,
                "exact_source_gaps": 0, "pending": 1,
                "new_provider_attempts": 0, "observed_credits_this_invocation": 0,
                "last_observed_provider_remaining": None,
                "verified_and_new_raw_body_bytes": 100}
    result = bulk.run_bulk_2022(
        settings,
        max_total_observed_credits=1,
        source_builder=lambda *_a, **_k: (manifest, sources),
        source_reader=complete,
        source_runner=lambda *_a, **_k: pytest.fail("complete chains must be reused"),
        quote_plan_builder=lambda *_a, **_k: plan, quote_runner=quote,
        authorize=True, paid=True, private=True, token="synthetic",
    )
    assert result["status"] == "SOURCE_COMPLETE_QUOTES_PARTIAL_SAFE_STOP"
    assert result["quote_pending"] == 1
    assert result["total_observed_credits"] == 0


def test_invalid_base_plan_refuses_all_provider_attempts(tmp_path, monkeypatch):
    settings = _base(tmp_path, monkeypatch)
    path = tmp_path / bulk.PLAN_REL / "through_shard_025.json"
    val = json.loads(path.read_text(encoding="utf-8"))
    val["unique_exact_quote_series"] += 1
    path.write_text(json.dumps(val), encoding="utf-8")
    with pytest.raises(CandidateChainCacheError, match="base quote plan"):
        bulk.run_bulk_2022(
            settings, authorize=True, paid=True, private=True, token="synthetic",
            source_builder=lambda *_a, **_k: pytest.fail("no source acquisition"),
        )


def test_explicit_authorization_and_worker_bounds_fail_before_provider(tmp_path, monkeypatch):
    settings = _base(tmp_path, monkeypatch)
    for kwargs in (
        {"authorize": False, "paid": True, "private": True, "token": "x"},
        {"authorize": True, "paid": True, "private": True, "token": ""},
        {"authorize": True, "paid": True, "private": True, "token": "x",
         "source_worker_ceiling": 9},
        {"authorize": True, "paid": True, "private": True, "token": "x",
         "quote_worker_ceiling": 25},
    ):
        with pytest.raises(CandidateChainCacheError):
            bulk.run_bulk_2022(
                settings, source_builder=lambda *_a, **_k: pytest.fail("no work"),
                **kwargs,
            )



def test_original_bulk_process_lock_is_not_removed_if_another_process_owns_it(
    tmp_path, monkeypatch,
):
    import scripts.run_marketdata_2022_bulk_acquisition_v1 as cli
    settings = _settings(tmp_path)
    lock = tmp_path / "data/options/manifests/marketdata_bulk_2022_active_v1.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("pid=someone-else", encoding="utf-8")
    snapshot = SimpleNamespace(
        disk_free_gib=200.0,
        category_usage_gib={"options_candidate_cache": 0.1},
        category_quota_gib={"options_candidate_cache": 120.0},
    )
    monkeypatch.setattr(cli, "load_settings", lambda *_a: settings)
    monkeypatch.setattr(cli, "inspect_research_storage", lambda *_a: snapshot)
    monkeypatch.setattr(cli, "run_bulk_2022",
                        lambda *_a, **_kw: pytest.fail("must refuse concurrent process"))
    assert cli.main([]) == 3
    assert lock.read_text(encoding="utf-8") == "pid=someone-else"



def test_batch_native_source_reads_all_unfrozen_new_shards_once(tmp_path, monkeypatch):
    from datetime import UTC, date, datetime
    setting = SimpleNamespace(project_root=tmp_path, resolved_path=lambda p: tmp_path / p)
    cases = [
        SimpleNamespace(
            opportunity_id=f"case-{i:05d}",
            ticker="ABCD", native_timeframe="1d", direction="LONG",
            signal_session=date(2022, 1, 3),
            entry_utc=datetime(2022, 1, 4, tzinfo=UTC),
        )
        for i in range(2812)
    ]
    monkeypatch.setattr(bulk.shards, "_key",
                        lambda item: ("ABCD", item.opportunity_id, "2022-03-18"))
    keys = sorted(
        [(x.ticker, x.opportunity_id, "2022-03-18") for x in cases],
        key=lambda k: (bulk.shards._fingerprint({"salt": bulk.shards.SALT, "key": k}), k),
    )
    monkeypatch.setattr(
        bulk, "FROZEN_GLOBAL_2022_KEYS_FINGERPRINT", bulk.shards._fingerprint(keys),
    )
    prior = ({"plan_fingerprint": bulk.shards.FROZEN_PRIOR_PLAN},
             {f"old-{i}" for i in range(36)}, {("OLD", "test", "2022-03-18")})
    loader_calls = []
    native_calls = []
    selected_ids = []
    def loader(*a, **kw):
        loader_calls.append(1)
        return cases, {"source_integrity_fingerprint": "verified-replay"}
    def native(root, reps):
        assert root == tmp_path
        native_calls.append(1)
        selected_ids.extend(x.opportunity_id for x in reps)
        return {x.opportunity_id: 100.0 for x in reps}, {
            "source_fingerprint": "accepted-stock-daily",
            "protected_master_return_rows_read": 0,
            "native_raw_source": {"verified_native_raw_unit_bindings": ["original-sha"]},
        }
    progress = []
    reader = bulk._batched_native_open_reader(
        setting, loader, prior, native_reader=native, progress=progress.append,
    )
    assert len(loader_calls) == len(native_calls) == 1
    assert len(selected_ids) == 1772
    result, source = reader(tmp_path, [cases[0]]) if cases[0].opportunity_id in selected_ids else (
        reader(tmp_path, [next(x for x in cases if x.opportunity_id in selected_ids)]))
    assert len(result) == 1
    assert source["protected_master_return_rows_read"] == 0
    assert progress[0]["stage"] == "BULK_NATIVE_RAW_ONCE"
    assert progress[0]["unique_native_opens"] == 1772
    with pytest.raises(CandidateChainCacheError, match="unverified opportunity"):
        reader(tmp_path, [SimpleNamespace(opportunity_id="unseen")])
    with pytest.raises(CandidateChainCacheError, match="project path"):
        reader(tmp_path / "elsewhere", [])

    # All original bound shards now exist: subsequent resume skips both
    # stock replay/native-unit scans and uses existing original SHA bindings.
    for i in range(26, 71):
        path = bulk.shards._binding_path(setting, i)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original-intact-source-binding", encoding="utf-8")
    reader2 = bulk._batched_native_open_reader(
        setting,
        lambda *_a, **_k: pytest.fail("native replay must be skipped on fully bound resume"),
        prior,
        native_reader=native,
    )
    assert reader2 is native
