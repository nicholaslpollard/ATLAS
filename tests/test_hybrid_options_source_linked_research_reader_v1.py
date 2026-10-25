from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from packages.data import hybrid_options_derived_dte_index_v1 as index
from packages.data import hybrid_options_source_linked_research_reader_v1 as v15
from packages.data import hybrid_options_unattended_campaign_v1 as v12
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.providers.thetadata.client import _canonical_bytes
from scripts import audit_hybrid_options_source_linked_research_v1 as cli


class FakeSettings:
    def __init__(self, root):
        self.root = root
        (root / "data/options/manifests").mkdir(parents=True)
    def resolved_path(self, path):
        return self.root / path
    def assert_external_storage_binding(self, name):
        assert name == "options"


def spy_row():
    day = "2019-07-08"
    params = {
        "symbol": "SPY", "start_date": "20190708",
        "end_date": "20190708", "time_of_day": "10:00:00.000",
        "right": "both", "max_dte": 45, "strike_range": 2,
        "expiration": "*", "strike": "*", "format": "json",
    }
    result = _entry(
        "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE", "a" * 64, "b" * 64,
        {"endpoint": "/v3/option/at_time/quote", "params": params},
        role="WEEKLY_ENTRY_DECISION", anchor=True,
    )
    result["priority"] = 1
    return result


def quote(exp, strike, right="CALL", *, bid=1.0, ask=1.1,
          stamp="2019-07-08T09:59:57-04:00"):
    return {
        "symbol": "SPY", "expiration": exp, "strike": strike,
        "right": right, "timestamp": stamp, "bid": bid, "ask": ask,
        "bid_size": 4, "ask_size": 8, "bid_exchange": 1,
        "ask_exchange": 2, "bid_condition": 0, "ask_condition": 0,
    }


def write_source(settings, row, quotes):
    qid = row["query_id"]
    raw = _canonical_bytes(quotes)
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    target = v12._archive_path(settings, qid)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(packed)
    src = {
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(raw), "compressed_bytes": len(packed),
        "observed_rows": len(quotes),
        "source_coverage_proven": False, "simulator_ready": False,
    }
    started = v12._evidence({
        "contract": v12.CONTRACT, "kind": "started",
        "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
        "manifest_fingerprint": index.PINNED_MANIFEST_FINGERPRINT,
        "query_id": qid,
        "original_query_fingerprint": row["origin_query_fingerprint"],
        "sdk_kwargs": index.validate_exact_request(row),
        "simulator_ready": False, "source_coverage_proven": False,
    })
    v12._write_receipt(settings, qid, "started", started)
    terminal = v12._evidence({
        "contract": v12.CONTRACT, "kind": "terminal",
        "manifest_fingerprint": index.PINNED_MANIFEST_FINGERPRINT,
        "query_id": qid,
        "started_fingerprint": started["fingerprint"],
        "state": "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
        "archive": src, "diagnostic_fingerprint": None,
        "error_type": None,
        "source_coverage_proven": False, "simulator_ready": False,
    })
    v12._write_receipt(settings, qid, "terminal", terminal)
    return target


@pytest.fixture
def accepted(tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    row = spy_row()
    original = [
        quote("2019-09-20", 280.0, "CALL"),  # outside 45 DTE
        quote("2019-08-02", 290.0, "CALL"),
        quote("2019-08-02", 290.0, "PUT"),
        quote("2019-08-02", 295.0, "CALL", bid=1.0, ask=2.0),
        quote("2019-08-02", 295.0, "PUT"),
        quote("2019-08-16", 300.0, "CALL"),
        quote("2019-07-19", 305.0, "PUT"),  # under 14 DTE
    ]
    archive = write_source(settings, row, original)
    frozen = {
        "manifest_fingerprint": index.PINNED_MANIFEST_FINGERPRINT,
        "source_request_count": 9866,
        "requests": [row],
    }
    monkeypatch.setattr(v15, "_load_full_manifest", lambda *_: frozen)
    monkeypatch.setattr(index, "_load_full_manifest", lambda *_: frozen)
    monkeypatch.setattr(index, "_safe_storage", lambda *_: {
        "safe": True,
        "available_after_hourly_reservations": 40 * 1024**3,
    })
    created = index.build_dte_reference_indices(
        settings, Path("frozen"), Path("candidate"), write_indexes=True,
    )
    assert created["new_immutable_indices"] == 1
    return settings, row, original, archive


def test_read_original_selected_quote_dicts_without_provider_or_write(accepted):
    settings, row, original, archive = accepted
    before = archive.read_bytes()
    selected = v15.read_selected_original_observations(settings, row)
    assert selected["query_id"] == row["query_id"]
    assert selected["source_row_positions"] == (1, 2, 3, 4, 5, 6)
    assert selected["original_source_row_count"] == 7
    assert len(selected["selected_quotes"]) == 6
    assert selected["selected_quotes"][0] == original[1]
    assert selected["selected_quotes"][-1] == original[6]
    assert selected["local_selection_is_provider_scoped"] is False
    assert selected["source_is_execution_admissible"] is False
    assert selected["simulator_ready"] is False
    assert selected["provider_requests"] == 0
    assert archive.read_bytes() == before


def test_observed_call_put_pairs_are_not_chain_completeness(accepted):
    settings, row, original, archive = accepted
    data = v15.read_selected_original_observations(settings, row)
    report = v15.summarize_selected_chain(data)
    assert report["v14_in_range_source_rows"] == 6
    assert report["research_window_observed_rows"] == 5
    assert report["observed_expirations"] == 2
    assert report["observed_call_put_strike_pairs"] == 2
    assert report["observed_pairs_passing_freshness_spread_only"] == 1
    assert report["research_window_stale_rows"] == 0
    assert report["research_window_wide_spread_rows"] == 1
    assert report["per_expiration"][0]["expiration"] == "2019-08-02"
    assert report["per_expiration"][0]["observed_call_put_pairs"] == 2
    assert report["strike_universe_completeness_proven"] is False
    assert report["point_in_time_underlying_spot_bound"] is False
    assert report["historical_open_interest_bound"] is False
    assert report["execution_admissible"] is False
    assert report["simulator_ready"] is False


def test_freshness_gate_discards_stale_pair_without_changing_quotes(accepted):
    settings, row, original, archive = accepted
    data = v15.read_selected_original_observations(settings, row)
    older = dict(data)
    original_quotes = list(older["selected_quotes"])
    original_quotes[1] = dict(original_quotes[1])
    original_quotes[1]["timestamp"] = "2019-07-08T09:58:20-04:00"
    older["selected_quotes"] = tuple(original_quotes)
    report = v15.summarize_selected_chain(older)
    assert report["research_window_stale_rows"] == 1
    assert report["observed_call_put_strike_pairs"] == 2
    assert report["observed_pairs_passing_freshness_spread_only"] == 0
    assert report["execution_admissible"] is False


def test_reject_future_timestamp(accepted):
    settings, row, original, archive = accepted
    data = v15.read_selected_original_observations(settings, row)
    altered = dict(data)
    quotes = list(altered["selected_quotes"])
    quotes[0] = dict(quotes[0], timestamp="2019-07-08T10:00:01-04:00")
    altered["selected_quotes"] = tuple(quotes)
    with pytest.raises(v15.HybridSourceLinkedReaderError, match="CAUSAL"):
        v15.summarize_selected_chain(altered)


def test_reject_forged_execution_authority(accepted):
    settings, row, original, archive = accepted
    data = v15.read_selected_original_observations(settings, row)
    forged = dict(data, simulator_ready=True)
    with pytest.raises(v15.HybridSourceLinkedReaderError, match="AUTHORITY"):
        v15.summarize_selected_chain(forged)
    forged = dict(data, local_selection_is_provider_scoped=True)
    with pytest.raises(v15.HybridSourceLinkedReaderError, match="AUTHORITY"):
        v15.summarize_selected_chain(forged)


def test_reject_invalid_research_dte_and_spread_scope(accepted):
    settings, row, original, archive = accepted
    data = v15.read_selected_original_observations(settings, row)
    for kwargs in (
        {"dte_min": 30, "dte_max": 20},
        {"dte_min": 0, "dte_max": 46},
        {"max_quote_age_seconds": -1},
        {"max_spread_to_mid": 0},
    ):
        with pytest.raises(v15.HybridSourceLinkedReaderError, match="PARAMETERS"):
            v15.summarize_selected_chain(data, **kwargs)


def test_fail_closed_if_original_source_bytes_tampered(accepted):
    settings, row, original, archive = accepted
    archive.write_bytes(b"corrupted")
    with pytest.raises(Exception):
        v15.read_selected_original_observations(settings, row)


def test_fail_closed_if_immutable_index_tampered(accepted):
    settings, row, original, archive = accepted
    path = next(p for p in settings.resolved_path(index.OUTPUT_REL).rglob("*.json"))
    content = json.loads(path.read_bytes())
    content["original_row_indices"] = [0]
    path.write_text(json.dumps(content))
    with pytest.raises(index.HybridDteIndexError):
        v15.read_selected_original_observations(settings, row)


def test_missing_index_requires_explicit_v14_prior_step(accepted):
    settings, row, original, archive = accepted
    path = next(p for p in settings.resolved_path(index.OUTPUT_REL).rglob("*.json"))
    path.unlink()
    with pytest.raises(v15.HybridSourceLinkedReaderError, match="INDEX_NOT_PRESENT"):
        v15.read_selected_original_observations(settings, row)


def test_census_source_read_only_and_no_outcomes(accepted):
    settings, row, original, archive = accepted
    before = archive.read_bytes()
    report = v15.audit_frozen_indexed_chains(
        settings, Path("frozen"), Path("candidate"),
    )
    assert report["sources_inspected"] == 1
    assert report["original_rows"] == 7
    assert report["v14_selected_rows"] == 6
    assert report["research_14_45_dte_observed_rows"] == 5
    assert report["observed_call_put_strike_pairs"] == 2
    assert report["pairs_passing_freshness_and_spread_only"] == 1
    assert report["simulator_ready"] is False
    assert report["protected_outcomes_read"] == 0
    assert report["provider_requests"] == 0
    assert report["files_written"] == 0
    assert archive.read_bytes() == before


def test_cli_has_no_provider_or_source_write(accepted, monkeypatch, capsys):
    settings, row, original, archive = accepted
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    assert cli.main([]) == 0
    output = capsys.readouterr().out
    assert "indexed_archives=1 original_rows=7 v14_in_dte_rows=6" in output
    assert "observed_call_put_pairs=2 fresh_tight_pairs=1" in output
    assert "simulator_ready=False" in output
    assert "files_written=0" in output
