from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_additive_2022_shards_v1 as additive
from packages.data import marketdata_accepted_stock_candidate_export_v1 as exporter
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _fixture(tmp_path):
    settings = SimpleNamespace(
        project_root=tmp_path, resolved_path=lambda path: tmp_path / path,
    )
    prior_path = additive._bound_path(settings, 2022, 3)
    prior_path.parent.mkdir(parents=True, exist_ok=True)
    prior_path.write_text("{}")
    prior_rows = [{"opportunity_id": f"orig{i}"} for i in range(36)]
    old_file = tmp_path / "original.json"
    old_file.write_text(json.dumps({"contract": exporter.CONTRACT, "year": 2022,
                                    "rows": prior_rows}))
    sha = additive._sha(old_file)
    old_plan = {
        "plan_fingerprint": additive.FROZEN_PRIOR_PLAN,
        "opportunities": 36, "shared_chain_requests": 36,
        "requests": [
            {"ticker": "SPY" if i == 0 else f"T{i:03d}",
             "params": {"date": "2022-01-03", "expiration": "2022-02-18"}}
            for i in range(36)
        ],
    }
    bound = {"cohort_id": additive.FROZEN_PRIOR_COHORT, "source_sha256": sha}
    def prepare(*args, **kwargs):
        return old_plan, old_file, bound, "REUSED_IMMUTABLE_EXPORTED_COHORT"
    old_state = {"pending": 0, "reused": 33, "no_data_verified": 3}
    def prior_preview(*args, **kwargs):
        return old_state
    def make_item(identifier, ticker):
        return SimpleNamespace(
            opportunity_id=identifier, ticker=ticker,
            signal_session=date(2022, 1, 3),
            entry_utc=datetime(2022, 1, 4, 14, 30, tzinfo=UTC),
            native_timeframe="1d", direction="LONG",
            instrument_id="instrument-" + identifier, policy_id="policy-v1",
        )
    items = [make_item("orig0", "SPY"), make_item("new-clash", "SPY")] + [
        make_item(f"add-{i:02d}", f"Z{i:03d}") for i in range(45)
    ]
    loads = []
    def loader(*args, **kwargs):
        loads.append(kwargs)
        return items, {"source_integrity_fingerprint": "a" * 64,
                       "conditioning_analysis_fingerprint": "b" * 64}
    native_calls = []
    def native(project_root, selected):
        native_calls.append(tuple(x.opportunity_id for x in selected))
        return {x.opportunity_id: 100.0 for x in selected}, {
            "protected_master_return_rows_read": 0,
            "source_fingerprint": "c" * 64,
            "manifest_sha256": "d" * 64,
            "native_raw_source": {"verified_native_raw_unit_count": 1},
        }
    return settings, prepare, prior_preview, loader, native, loads, native_calls, old_state


def _build(settings, prepare, prior, loader, native, *, idx=0):
    return additive.prepare_additive_shard(
        settings, shard_index=idx, preparer=prepare,
        runner=prior, loader=loader, native_reader=native,
    )


def test_additive_shard_is_new_and_excludes_old_entire_underlying_date_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, previous, loader, native, loads, calls, _ = _fixture(tmp_path)
    plan, source_path, binding, action = _build(settings, prep, previous, loader, native)
    assert action == "WRITTEN_NEW_ADDITIVE_SHARD"
    assert binding["selected_opportunities"] == 40
    assert binding["shared_chains"] == 40
    assert plan["opportunities"] == 40
    source = json.loads(source_path.read_text())
    assert source["eligible_daily_long_cases"] == 47
    assert source["excluded_original_opportunity_ids"] == 1
    assert source["excluded_colliding_original_query_keys"] == 1
    assert source["total_additive_shards"] == 2
    assert "SPY" not in {r["ticker"] for r in plan["requests"]}
    assert not any(x["opportunity_id"] == "new-clash" for x in source["rows"])
    assert len(calls) == 1 and len(calls[0]) == 40
    assert source["protected_master_return_rows_read"] == 0
    assert binding["provider_reads"] == 0


def test_reused_exact_shard_does_not_reload_accepted_2022_or_native_units(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)
    original = _build(settings, prep, prev, loader, native)
    restored = additive.prepare_additive_shard(
        settings, shard_index=0, preparer=prep, runner=prev,
        loader=lambda *_a, **_k: pytest.fail("source should not reload"),
        native_reader=lambda *_a, **_k: pytest.fail("native units should not reload"),
    )
    assert restored[0] == original[0]
    assert restored[2] == original[2]
    assert restored[3] == "REUSED_IMMUTABLE_ADDITIVE_SHARD"
    assert len(loads) == 1 and len(calls) == 1


def test_shards_cover_disjoint_physical_request_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)
    a = _build(settings, prep, prev, loader, native, idx=0)[0]
    b = _build(settings, prep, prev, loader, native, idx=1)[0]
    assert a["shared_chain_requests"] == 40
    assert b["shared_chain_requests"] == 5
    ia = {r["request_identity"] for r in a["requests"]}
    ib = {r["request_identity"] for r in b["requests"]}
    assert ia.isdisjoint(ib)


def test_original_2022_must_be_complete_before_new_provider_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, state = _fixture(tmp_path)
    state["pending"] = 17
    with pytest.raises(CandidateChainCacheError, match="finish and verify"):
        _build(settings, prep, prev, loader, native)
    assert not loads and not calls


def test_source_mutation_and_unsupported_shard_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)
    _, path, _, _ = _build(settings, prep, prev, loader, native)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(CandidateChainCacheError, match="SHA lineage"):
        _build(settings, prep, prev, loader, native)
    with pytest.raises(CandidateChainCacheError, match="beyond"):
        _build(settings, prep, prev, loader, native, idx=2)


def test_prior_missing_binding_refuses_without_implicit_export(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)
    additive._bound_path(settings, 2022, 3).unlink()
    with pytest.raises(CandidateChainCacheError, match="has not been exported"):
        _build(settings, prep, prev, loader, native)
    assert not loads


def test_real_2022_holiday_shift_has_no_frozen_28_to_60_day_expiry():
    # March 18 is a trading Friday; April's standard expiration shifts to
    # April 14 for Good Friday (27 days), then May 20 is 63 days away.
    item = SimpleNamespace(ticker="SPY", signal_session=date(2022, 3, 18))
    with pytest.raises(exporter.CandidateStockExportError, match="no bounded exchange monthly expiry"):
        additive._key(item)


def test_expiry_gap_is_accounted_for_not_silently_erased(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)
    original_key = additive._key

    def key_with_one_known_gap(item):
        if item.opportunity_id == "add-00":
            raise exporter.CandidateStockExportError("no bounded exchange monthly expiry is available")
        return original_key(item)

    monkeypatch.setattr(additive, "_key", key_with_one_known_gap)
    plan, source_path, binding, _ = _build(settings, prep, prev, loader, native)
    bundle = json.loads(source_path.read_text())
    assert bundle["eligible_daily_long_cases"] == 47
    assert bundle["excluded_monthly_expiry_window_cases"] == 1
    assert bundle["monthly_expiry_window_exclusions"] == [{
        "opportunity_id": "add-00",
        "ticker": "Z000",
        "snapshot_date": "2022-01-03",
        "reason": "NO_MONTHLY_EXPIRY_IN_28_TO_60_DAY_WINDOW",
    }]
    assert bundle["monthly_expiry_window_exclusions_fingerprint"] == additive._fingerprint(
        bundle["monthly_expiry_window_exclusions"]
    )
    assert "add-00" not in {row["opportunity_id"] for row in bundle["rows"]}
    assert binding["excluded_monthly_expiry_window_cases"] == 1
    assert plan["opportunities"] == 40


def test_unrelated_source_calendar_error_is_not_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)
    def unexpected_error(item):
        raise exporter.CandidateStockExportError("unexpected accepted-calendar mismatch")
    monkeypatch.setattr(additive, "_key", unexpected_error)
    with pytest.raises(exporter.CandidateStockExportError, match="unexpected accepted-calendar mismatch"):
        _build(settings, prep, prev, loader, native)
    assert not calls
    assert not additive._binding_path(settings, 0).exists()


def test_same_physical_group_keeps_all_accepted_ids_with_one_native_raw_read(tmp_path, monkeypatch):
    monkeypatch.setattr(additive, "_require_external", lambda *_: None)
    settings, prep, prev, loader, native, loads, calls, _ = _fixture(tmp_path)

    def duplicate_loader(*args, **kwargs):
        rows, report = loader(*args, **kwargs)
        duplicated = []
        for row in rows:
            duplicated.append(row)
            if row.opportunity_id.startswith("add-"):
                clone = SimpleNamespace(**vars(row))
                clone.opportunity_id = row.opportunity_id + "-alternate-policy"
                clone.instrument_id = "alternate-" + row.instrument_id
                duplicated.append(clone)
        return duplicated, report

    plan, source_path, binding, _ = _build(
        settings, prep, prev, duplicate_loader, native,
    )
    bundle = json.loads(source_path.read_text())
    assert bundle["eligible_daily_long_cases"] == 92
    assert binding["selected_opportunities"] == 40
    assert binding["covered_same_key_alternate_opportunity_ids"] == 40
    assert bundle["covered_same_key_alternate_opportunity_ids"] == 40
    assert len(calls) == 1 and len(calls[0]) == 40
    assert all(len(group["all_accepted_member_ids"]) == 2
               for group in bundle["chosen_key_member_ids"])
    assert plan["shared_chain_requests"] == 40
    assert bundle["representative_policy"] == (
        "LEXICOGRAPHIC_FIRST_ID_PER_PHYSICAL_KEY_NO_OUTCOMES"
    )
