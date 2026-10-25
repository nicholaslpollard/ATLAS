from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from packages.data import hybrid_options_saved_scope_quality_v1 as quality
from packages.data import hybrid_options_unattended_campaign_v1 as camp
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.providers.thetadata.client import _canonical_bytes
from scripts import audit_hybrid_options_saved_scope_quality_v1 as cli


class Settings:
    def __init__(self, root):
        self.root = root
        (root / "data/options/manifests").mkdir(parents=True)
    def resolved_path(self, relative):
        return self.root / relative
    def assert_external_storage_binding(self, name):
        assert name == "options"


def _row(symbol, date, priority):
    stamp = date.replace("-", "")
    row = _entry(
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES",
        "a" * 64, "b" * 64,
        {"endpoint": "/v3/option/at_time/quote", "params": {
            "symbol": symbol, "start_date": stamp,
            "end_date": stamp, "time_of_day": "09:35:00.000",
            "right": "call", "max_dte": 75, "strike_range": None,
            "expiration": "*", "strike": "*", "format": "json",
        }},
        role="0935_CALL_ENTRY_DISCOVERY", anchor=False,
    )
    row["priority"] = priority
    return row


def _quote(symbol, date, expiry, strike=30.0, *,
           bid=1.2, ask=1.3, right="CALL",
           stamp_suffix="T09:34:55-05:00"):
    return {
        "symbol": symbol, "expiration": expiry, "strike": strike,
        "right": right, "timestamp": date + stamp_suffix,
        "bid": bid, "ask": ask, "bid_size": 3, "ask_size": 4,
        "bid_exchange": 1, "ask_exchange": 2,
        "bid_condition": 0, "ask_condition": 0,
    }


def _save(settings, row, original):
    qid = row["query_id"]
    payload = _canonical_bytes(original)
    packed = gzip.compress(payload, compresslevel=9, mtime=0)
    path = camp._archive_path(settings, qid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(packed)
    archive = {
        "original_sha256": hashlib.sha256(payload).hexdigest(),
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(payload),
        "compressed_bytes": len(packed),
        "observed_rows": len(original),
        "source_coverage_proven": False,
        "simulator_ready": False,
    }
    started = camp._evidence({
        "contract": camp.CONTRACT, "kind": "started",
        "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
        "manifest_fingerprint":
            "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63",
        "query_id": qid,
        "original_query_fingerprint": row["origin_query_fingerprint"],
        "sdk_kwargs": quality.validate_exact_request(row),
        "simulator_ready": False, "source_coverage_proven": False,
    })
    camp._write_receipt(settings, qid, "started", started)
    finish = camp._evidence({
        "contract": camp.CONTRACT, "kind": "terminal",
        "manifest_fingerprint":
            "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63",
        "query_id": qid,
        "started_fingerprint": started["fingerprint"],
        "state": "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
        "archive": archive,
        "diagnostic_fingerprint": None,
        "error_type": None,
        "simulator_ready": False, "source_coverage_proven": False,
    })
    camp._write_receipt(settings, qid, "terminal", finish)
    return path


@pytest.fixture
def saved(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    rows = [
        _row("AAL", "2021-11-30", 1),
        _row("AAPL", "2021-12-01", 2),
    ]
    quotes1 = [
        _quote("AAL", "2021-11-30", "2022-01-14"),
        _quote("AAL", "2021-11-30", "2022-06-17", strike=35.0),
    ]
    quotes2 = [
        _quote("AAPL", "2021-12-01", "2022-01-14"),
        _quote("AAPL", "2021-12-01", "2022-05-20", strike=35.0),
    ]
    originals = [_save(settings, rows[0], quotes1),
                 _save(settings, rows[1], quotes2)]
    full = {
        "manifest_fingerprint":
            "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63",
        "source_request_count": 9866,
        "requests": rows,
    }
    monkeypatch.setattr(
        quality, "_load_full_manifest", lambda *_: full,
    )
    return settings, rows, originals


def test_read_only_census_reconciles_two_out_of_dte_archives(saved):
    settings, rows, original_paths = saved
    report = quality.audit_campaign_scope(settings, Path("v9"), Path("candidate"))
    assert report["archived_sources"] == 2
    assert report["attempted_source_ids"] == 2
    assert report["sources_with_dte_overruns"] == 2
    assert report["sources_with_non_dte_semantic_defects"] == 0
    assert report["total_original_quote_rows"] == 4
    assert report["observed_in_requested_dte_rows"] == 2
    assert report["observed_outside_requested_dte_rows"] == 2
    assert report["observed_positive_two_sided_rows"] == 4
    assert report["dte_buckets"]["15_45"] == 2
    assert report["dte_buckets"]["181_PLUS"] == 2
    assert report["provider_requests"] == 0
    assert report["source_chain_completeness_proven"] is False
    assert report["simulator_ready"] is False
    assert report["fingerprint"] == quality._fingerprint({
        k: v for k, v in report.items() if k != "fingerprint"
    })
    for i, path in enumerate(original_paths):
        assert len(json.loads(gzip.decompress(path.read_bytes()))) == 2


def test_corrupted_archive_prevents_audit_and_does_not_write(saved):
    settings, rows, paths = saved
    paths[0].write_bytes(b"damaged")
    with pytest.raises(camp.HybridCampaignError):
        quality.audit_campaign_scope(settings, Path("v9"), Path("candidate"))
    assert paths[0].read_bytes() == b"damaged"


def test_bad_quote_diagnostic_counts_without_source_promotion(saved, monkeypatch):
    settings, rows, paths = saved
    # Pure quote-check helper, no source/data mutation.
    content = [
        _quote("AAPL", "2021-12-01", "2022-01-14",
               stamp_suffix="T09:35:01-05:00"),
        _quote("AAPL", "2021-12-01", "2022-04-15", strike=35.0),
    ]
    diag = quality._one_source_quality(rows[1], content)
    assert diag["other_invalid_rows"] == 1
    assert diag["outside_requested_dte"] == 1
    assert diag["in_requested_dte"] == 0
    assert diag["simulator_ready"] is False


def test_cli_is_provider_free_and_does_not_write(saved, monkeypatch, capsys):
    settings, rows, paths = saved
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    assert cli.main([]) == 0
    display = capsys.readouterr().out
    assert "OFFLINE_VERIFIED_ORIGINAL_ARCHIVE_READ_ONLY" in display
    assert "archived=2 attempted=2 scope_overruns=2" in display
    assert "provider_calls=0 files_written=0" in display
    assert not list(settings.root.rglob("scope_quality_report*.json"))
