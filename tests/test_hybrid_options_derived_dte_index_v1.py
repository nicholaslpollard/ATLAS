from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from packages.data import hybrid_options_derived_dte_index_v1 as index
from packages.data import hybrid_options_unattended_campaign_v1 as v12
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.providers.thetadata.client import _canonical_bytes
from scripts import build_hybrid_options_derived_dte_index_v1 as cli


class FakeSettings:
    def __init__(self, path):
        self.root = path
        (path / "data/options/manifests").mkdir(parents=True)
    def assert_external_storage_binding(self, label):
        assert label == "options"
    def resolved_path(self, rel):
        return self.root / rel


def row(symbol, day, priority):
    d = day.replace("-", "")
    result = _entry(
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES",
        "a" * 64, "b" * 64,
        {"endpoint": "/v3/option/at_time/quote",
         "params": {
             "symbol": symbol, "start_date": d, "end_date": d,
             "time_of_day": "09:35:00.000",
             "right": "call", "max_dte": 75, "strike_range": None,
             "expiration": "*", "strike": "*", "format": "json",
         }},
        role="0935_CALL_ENTRY_DISCOVERY", anchor=False,
    )
    result["priority"] = priority
    return result


def quote(symbol, day, expiry, strike, *, right="CALL"):
    return {
        "symbol": symbol, "expiration": expiry, "strike": strike,
        "right": right, "timestamp": day + "T09:34:55-05:00",
        "bid": 1.10, "ask": 1.20, "bid_size": 4, "ask_size": 5,
        "bid_exchange": 1, "ask_exchange": 2,
        "bid_condition": 0, "ask_condition": 0,
    }


def write_source(s, r, rows):
    qid = r["query_id"]
    raw = _canonical_bytes(rows)
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    path = v12._archive_path(s, qid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(packed)
    archive = {
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(raw),
        "compressed_bytes": len(packed),
        "observed_rows": len(rows),
        "source_coverage_proven": False, "simulator_ready": False,
    }
    start = v12._evidence({
        "contract": v12.CONTRACT, "kind": "started",
        "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
        "manifest_fingerprint": index.PINNED_MANIFEST_FINGERPRINT,
        "query_id": qid,
        "original_query_fingerprint": r["origin_query_fingerprint"],
        "sdk_kwargs": index.validate_exact_request(r),
        "source_coverage_proven": False, "simulator_ready": False,
    })
    v12._write_receipt(s, qid, "started", start)
    terminal = v12._evidence({
        "contract": v12.CONTRACT, "kind": "terminal",
        "manifest_fingerprint": index.PINNED_MANIFEST_FINGERPRINT,
        "query_id": qid, "started_fingerprint": start["fingerprint"],
        "state": "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
        "archive": archive, "diagnostic_fingerprint": None,
        "error_type": None,
        "source_coverage_proven": False, "simulator_ready": False,
    })
    v12._write_receipt(s, qid, "terminal", terminal)
    return path


@pytest.fixture
def sample(tmp_path, monkeypatch):
    s = FakeSettings(tmp_path)
    rows = [row("AAL", "2021-11-30", 1),
            row("AAPL", "2021-12-01", 2)]
    # Original order is preserved exactly, even if distant options are
    # interleaved with in-scope options.
    quotes = [
        [
            quote("AAL", "2021-11-30", "2022-05-20", 20.0),
            quote("AAL", "2021-11-30", "2022-01-14", 25.0),
            quote("AAL", "2021-11-30", "2022-03-04", 30.0),
        ],
        [
            quote("AAPL", "2021-12-01", "2022-02-04", 100.0),
            quote("AAPL", "2021-12-01", "2022-06-17", 105.0),
        ],
    ]
    paths = [write_source(s, rows[i], quotes[i]) for i in range(2)]
    frozen = {
        "manifest_fingerprint": index.PINNED_MANIFEST_FINGERPRINT,
        "source_request_count": 9866, "requests": rows,
    }
    monkeypatch.setattr(index, "_load_full_manifest", lambda *_: frozen)
    monkeypatch.setattr(index, "_safe_storage", lambda *_: {
        "safe": True,
        "available_after_hourly_reservations": 100 * 1024**3,
    })
    return s, rows, paths, quotes


def test_preview_selects_row_indices_and_writes_nothing(sample):
    s, rows, paths, originals = sample
    report = index.build_dte_reference_indices(
        s, Path("manifest"), Path("plan"),
    )
    assert report["status"] == "DERIVED_INDEX_PREVIEW_ONLY"
    assert report["original_archives_scanned"] == 2
    assert report["in_requested_dte_references"] == 3
    assert report["outside_requested_dte_rows_not_indexed"] == 2
    assert report["new_immutable_indices"] == 0
    assert report["provider_requests"] == 0
    assert not s.resolved_path(index.OUTPUT_REL).exists()
    assert report["source_chain_completeness_proven"] is False


def test_immutable_write_and_verified_idempotent_replay(sample):
    s, rows, paths, original = sample
    before = [p.read_bytes() for p in paths]
    report = index.build_dte_reference_indices(
        s, Path("manifest"), Path("plan"), write_indexes=True,
    )
    assert report["new_immutable_indices"] == 2
    root = s.resolved_path(index.OUTPUT_REL)
    files = list(root.rglob("*.json"))
    assert len(files) == 2
    aal = next(json.loads(p.read_bytes()) for p in files
               if json.loads(p.read_bytes())["symbol"] == "AAL")
    assert aal["original_row_indices"] == [1, 2]
    assert aal["locally_selected_rows"] == 2
    assert aal["locally_excluded_over_dte_rows"] == 1
    assert aal["source_replaced_or_modified"] is False
    assert aal["simulator_ready"] is False
    assert aal["provider_requests"] == 0
    for p, data in zip(paths, before):
        assert p.read_bytes() == data
    second = index.build_dte_reference_indices(
        s, Path("manifest"), Path("plan"), write_indexes=True,
    )
    assert second["new_immutable_indices"] == 0
    assert second["already_immutable_indices"] == 2
    checked = index.verify_scoped_reference(s, rows[0])
    assert checked["selected"] == 2
    assert checked["original"] == 3
    assert checked["simulator_ready"] is False
    assert len(list(root.rglob("*.json"))) == 2


def test_original_compressed_sha_drift_blocks_without_repair(sample):
    s, rows, paths, originals = sample
    paths[0].write_bytes(b"damaged")
    with pytest.raises(Exception):
        index.build_dte_reference_indices(
            s, Path("manifest"), Path("plan"), write_indexes=True,
        )
    assert not s.resolved_path(index.OUTPUT_REL).exists()
    assert paths[0].read_bytes() == b"damaged"


def test_existing_index_mutation_fails_closed(sample):
    s, rows, paths, original = sample
    index.build_dte_reference_indices(
        s, Path("manifest"), Path("plan"), write_indexes=True,
    )
    index_file = next(p for p in s.resolved_path(index.OUTPUT_REL).rglob("*.json")
                      if rows[0]["query_id"] in p.name)
    altered = json.loads(index_file.read_bytes())
    altered["simulator_ready"] = True
    index_file.write_text(json.dumps(altered))
    with pytest.raises(index.HybridDteIndexError, match="CONTENT_DRIFT"):
        index.build_dte_reference_indices(
            s, Path("manifest"), Path("plan"), write_indexes=True,
        )


def test_conflicting_derivation_fingerprint_rejected(sample):
    s, rows, paths, originals = sample
    index.build_dte_reference_indices(
        s, Path("manifest"), Path("plan"), write_indexes=True,
    )
    original_index = next(p for p in s.resolved_path(index.OUTPUT_REL).rglob("*.json")
                          if rows[0]["query_id"] in p.name)
    conflicting = original_index.with_name(rows[0]["query_id"] + "_deadbeefdeadbeef.json")
    conflicting.write_bytes(b'{"not":"valid"}')
    with pytest.raises(index.HybridDteIndexError, match="CONFLICTING"):
        index.build_dte_reference_indices(
            s, Path("manifest"), Path("plan"),
        )


def test_uncertainty_never_issues_provider_or_simulation(sample, monkeypatch):
    s, rows, paths, originals = sample
    # No eligible source with invalid historical data can be indexed.
    broken = [dict(x) for x in originals[0]]
    broken[1]["timestamp"] = "2021-11-30T09:35:01-05:00"
    diag = index._one_source_quality(rows[0], broken)
    start = v12._read_receipt(v12._record_path(s, rows[0]["query_id"], "started"),
                              rows[0]["query_id"], "started")
    terminal = v12._read_receipt(v12._record_path(s, rows[0]["query_id"], "terminal"),
                                 rows[0]["query_id"], "terminal")
    with pytest.raises(index.HybridDteIndexError, match="SEMANTICS"):
        index._expected_index(rows[0], terminal, broken)


def test_write_blocked_by_options_storage_budget(sample, monkeypatch):
    s, rows, paths, originals = sample
    monkeypatch.setattr(
        index, "_safe_storage", lambda *_: {
            "safe": False, "available_after_hourly_reservations": 0,
        },
    )
    with pytest.raises(index.HybridDteIndexError, match="HEADROOM"):
        index.build_dte_reference_indices(
            s, Path("manifest"), Path("plan"), write_indexes=True,
        )
    assert not s.resolved_path(index.OUTPUT_REL).exists()


def test_cli_readonly_and_write_without_user_prompt(sample, monkeypatch, capsys):
    s, rows, paths, originals = sample
    monkeypatch.setattr(cli, "load_settings", lambda *_: s)
    assert cli.main([]) == 0
    assert "READ_ONLY_REFERENCE_PREVIEW" in capsys.readouterr().out
    assert not s.resolved_path(index.OUTPUT_REL).exists()
    assert cli.main(["--write-indexes"]) == 0
    out = capsys.readouterr().out
    assert "WRITE_IMMUTABLE_REFERENCE_INDEX_ONLY" in out
    assert "newly_written_indices=2" in out
    assert "provider_requests=0" in out
    assert "simulator_ready=False" in out
