from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data import marketdata_2022_native_batch_v1 as batch
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint


def test_once_only_native_full_cohort_then_same_sha_metadata_on_partial_resume(
    tmp_path, monkeypatch,
):
    setting = SimpleNamespace(
        project_root=tmp_path,
        resolved_path=lambda p: tmp_path / p,
    )
    cases = [
        SimpleNamespace(
            opportunity_id=f"case-{i:04d}",
            ticker="ABCD", native_timeframe="1d", direction="LONG",
            signal_session=date(2022, 1, 3),
            entry_utc=datetime(2022, 1, 4, tzinfo=UTC),
        )
        for i in range(2812)
    ]
    monkeypatch.setattr(
        batch.shards, "_key",
        lambda item: ("ABCD", item.opportunity_id, "2022-03-18"),
    )
    keys = sorted(
        [(x.ticker, x.opportunity_id, "2022-03-18") for x in cases],
        key=lambda x: (_fingerprint({"salt": batch.shards.SALT, "key": x}), x),
    )
    monkeypatch.setattr(batch, "FROZEN_CENSUS", _fingerprint(keys))
    prior = (
        {"plan_fingerprint": batch.shards.FROZEN_PRIOR_PLAN},
        {f"old-{i}" for i in range(36)},
        {("OLD", "2022-01-03", "2022-03-18")},
    )
    load_calls = []
    raw_calls = []
    rows = []
    def loader(*a, **kw):
        load_calls.append(1)
        return cases, {"source_integrity_fingerprint": "synthetic-replay"}
    def native(root, reps, *, progress=None):
        assert root == tmp_path
        raw_calls.append(1)
        if progress:
            progress("NATIVE_RAW_UNIT_VERIFIED", {"verified_units": 1, "total_units": 1})
        rows.extend(x.opportunity_id for x in reps)
        return {x.opportunity_id: 100.0 for x in reps}, {
            "source_fingerprint": "source-sha",
            "manifest_sha256": "native-manifest",
            "protected_master_return_rows_read": 0,
            "native_raw_source": {"verified_native_raw_unit_bindings": ["canonical-sha"]},
        }
    progress = []
    reader = batch.batched_native_reader(
        setting, loader, prior, native_reader=native, progress=progress.append,
    )
    assert len(load_calls) == len(raw_calls) == 1
    assert len(rows) == 1772
    assert progress[0]["stage"] == "BULK_NATIVE_RAW_PREFLIGHT"
    assert progress[-1]["stage"] == "BULK_NATIVE_RAW_VERIFIED_ONCE"
    selected = next(x for x in cases if x.opportunity_id in rows)
    prices, source = reader(tmp_path, [selected])
    assert prices == {selected.opportunity_id: 100.0}
    assert source["source_fingerprint"] == "source-sha"
    with pytest.raises(CandidateChainCacheError, match="unverified"):
        reader(tmp_path, [SimpleNamespace(opportunity_id="not-in-frozen-census")])
    # Partial restart still reads ALL original representatives so per-shard
    # source metadata cannot change depending on which shards finished.
    first = batch.shards._binding_path(setting, 26)
    first.parent.mkdir(parents=True)
    first.write_text("existing original binding", encoding="utf-8")
    reader2 = batch.batched_native_reader(
        setting, loader, prior, native_reader=native,
    )
    assert len(load_calls) == len(raw_calls) == 2
    prices2, source2 = reader2(tmp_path, [selected])
    assert prices2 == prices and source2 == source
    for i in range(26, 71):
        p = batch.shards._binding_path(setting, i)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("existing original binding", encoding="utf-8")
    assert batch.batched_native_reader(
        setting,
        lambda *_a, **_kw: pytest.fail("fully frozen restart must skip native scan"),
        prior, native_reader=native,
    ) is native


def test_native_source_mismatch_aborts_before_any_original_source_write(tmp_path, monkeypatch):
    setting = SimpleNamespace(project_root=tmp_path, resolved_path=lambda p: tmp_path / p)
    monkeypatch.setattr(batch.shards, "_key",
                        lambda x: ("ABCD", x.opportunity_id, "2022-03-18"))
    x = SimpleNamespace(
        opportunity_id="abc", ticker="ABCD", native_timeframe="1d",
        direction="LONG", signal_session=date(2022,1,3),
        entry_utc=datetime(2022,1,4,tzinfo=UTC),
    )
    with pytest.raises(CandidateChainCacheError, match="census"):
        batch.batched_native_reader(
            setting,
            lambda *_a, **_kw: ([x], {"source_integrity_fingerprint": "yes"}),
            ({"plan_fingerprint": batch.shards.FROZEN_PRIOR_PLAN}, set(), set()),
            native_reader=lambda *_a, **_kw: pytest.fail("should stop before raw read"),
        )
