from __future__ import annotations

from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import pytest

from packages.data import thetadata_hourly_source_canary_v1 as canary
from packages.data.hybrid_options_coverage_catalog_v1 import ingest_hourly_source
from packages.data.hybrid_options_lossless_archive_v1 import (
    HybridArchiveError, archive_existing_source,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)


class FakeSettings:
    def __init__(self, base):
        self.base = Path(base)
        (self.base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, name):
        assert name == "options"

    def resolved_path(self, relpath):
        return self.base / relpath


@pytest.fixture(autouse=True)
def synthetic_disk_headroom(monkeypatch):
    class Volume:
        free = 200 * 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Volume())


@pytest.fixture
def indexed_source(tmp_path):
    settings = FakeSettings(tmp_path)
    rows = tuple({
        "symbol": "SPY", "expiration": "2025-07-18",
        "strike": 500.0, "right": right,
        "timestamp": datetime(2025, 6, 9, 10, 30,
                              tzinfo=ZoneInfo("America/New_York")).isoformat(),
        "bid": 3.0, "ask": 3.1, "bid_size": 5, "ask_size": 6,
    } for right in ("CALL", "PUT"))
    original = _canonical_bytes(rows)
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        return ThetaDataResponse(
            http_status=200, rows=rows, headers={},
            response_bytes=len(original), elapsed_seconds=0.1,
            raw_body=original, transport=TRANSPORT,
            library_version=TARGET_LIBRARY_VERSION,
            provider_environment_fingerprint="a" * 64,
            evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
        )

    canary_receipt = canary.run_one_hourly_source_canary(
        settings, reader=reader,
        authorize_one_hourly_quote=True, confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert len(calls) == 1
    registered = ingest_hourly_source(
        settings, Path(canary_receipt["report_path"]),
    )
    assert registered["catalog_inserted"]
    assert registered["simulator_ready"] is False
    original_path = Path(json.loads(
        Path(canary_receipt["receipt_path"]).read_text(),
    )["body_path"])
    original_before = original_path.read_bytes()
    return settings, registered["source_id"], original_path, original_before


def test_preview_does_not_write_any_archive(indexed_source):
    settings, source_id, original, body = indexed_source
    report = archive_existing_source(settings, source_id)
    assert report["archive_present"] is False
    assert report["archive_inserted"] is False
    assert report["lossless_source_verification"] is True
    assert report["provider_requests"] == 0
    assert report["simulator_ready"] is False
    assert not Path(report["archive_path"]).exists()
    assert original.read_bytes() == body


def test_write_roundtrip_and_repeat_is_noop(indexed_source):
    settings, source_id, original, body = indexed_source
    first = archive_existing_source(settings, source_id, write_archive=True)
    assert first["archive_inserted"] is True
    assert first["archive_present"] is True
    assert first["original_source_preserved"] is True
    assert first["observed_quotes"] == 2
    assert first["compressed_bytes"] < first["original_bytes"]
    archive = Path(first["archive_path"])
    receipt_path = Path(first["receipt_path"])
    assert gzip.decompress(archive.read_bytes()) == body
    receipt = json.loads(receipt_path.read_text())
    assert receipt["original_sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["compressed_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert receipt["source_coverage_accepted"] is False
    assert receipt["simulator_ready"] is False
    assert receipt["compression"] == "gzip_level9_mtime0"
    assert archive.read_bytes()[4:8] == b"\x00\x00\x00\x00"
    original_compressed = archive.read_bytes()
    original_receipt = receipt_path.read_bytes()
    second = archive_existing_source(settings, source_id, write_archive=True)
    assert second["archive_inserted"] is False
    assert second["archive_present"] is True
    assert archive.read_bytes() == original_compressed
    assert receipt_path.read_bytes() == original_receipt
    assert original.read_bytes() == body


def test_partial_receipt_is_fail_closed_without_rewrite(indexed_source):
    settings, source_id, _, _ = indexed_source
    preview = archive_existing_source(settings, source_id)
    archive = Path(preview["archive_path"])
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"orphan")
    with pytest.raises(HybridArchiveError, match="INCOMPLETE_ARCHIVE"):
        archive_existing_source(settings, source_id, write_archive=True)
    assert archive.read_bytes() == b"orphan"


def test_modified_original_is_rejected_without_archive_write(indexed_source):
    settings, source_id, original, _ = indexed_source
    original.write_bytes(original.read_bytes() + b"changed")
    with pytest.raises(ValueError):
        archive_existing_source(settings, source_id, write_archive=True)


def test_archive_corruption_is_fail_closed(indexed_source):
    settings, source_id, _, _ = indexed_source
    first = archive_existing_source(settings, source_id, write_archive=True)
    archive = Path(first["archive_path"])
    archive.write_bytes(archive.read_bytes() + b"corrupt")
    with pytest.raises(HybridArchiveError, match="ARCHIVE_RECEIPT|ARCHIVE_GZIP"):
        archive_existing_source(settings, source_id, write_archive=True)


def test_receipt_corruption_is_fail_closed(indexed_source):
    settings, source_id, _, _ = indexed_source
    first = archive_existing_source(settings, source_id, write_archive=True)
    receipt_path = Path(first["receipt_path"])
    receipt = json.loads(receipt_path.read_text())
    receipt["simulator_ready"] = True
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(HybridArchiveError, match="ARCHIVE_RECEIPT"):
        archive_existing_source(settings, source_id, write_archive=True)


@pytest.mark.parametrize("source_id", [
    "", "nonhex", "a" * 63, "g" * 64, "../" + "a" * 64,
])
def test_invalid_source_identity_never_writes(indexed_source, source_id):
    settings, _, _, _ = indexed_source
    with pytest.raises(HybridArchiveError, match="INVALID_EXACT_SOURCE_ID"):
        archive_existing_source(settings, source_id, write_archive=True)


def test_legacy_catalog_source_cannot_be_mislabeled_simulation_ready(indexed_source):
    from packages.data.duckdb_connection import connect_utc
    from packages.data.hybrid_options_coverage_catalog_v1 import CATALOG_REL
    settings, source_id, _, _ = indexed_source
    db = settings.resolved_path(CATALOG_REL)
    con = connect_utc(db)
    try:
        con.execute("UPDATE source_units SET simulator_ready=TRUE")
    finally:
        con.close()
    with pytest.raises(HybridArchiveError, match="CATALOG_SOURCE_AUTHORITY_CHANGED"):
        archive_existing_source(settings, source_id, write_archive=True)
