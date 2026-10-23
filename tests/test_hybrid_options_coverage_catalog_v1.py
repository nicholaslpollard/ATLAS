from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from packages.data.duckdb_connection import connect_utc
from packages.data import thetadata_hourly_source_canary_v1 as canary
from packages.data import hybrid_options_coverage_catalog_v1 as hybrid
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT, ThetaDataResponse,
    _canonical_bytes,
)


class FakeSettings:
    def __init__(self, base):
        self.base = Path(base)
        (self.base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, name):
        assert name == "options"

    def resolved_path(self, relative):
        return self.base / relative


@pytest.fixture(autouse=True)
def fake_disk_headroom(monkeypatch):
    class Drive:
        free = 200 * 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Drive())


@pytest.fixture
def retained_source(tmp_path):
    settings = FakeSettings(tmp_path)

    def reader(**kwargs):
        assert kwargs == {
            "symbol": "SPY", "date_et": "2025-06-09",
            "right": "both", "max_dte": 45, "strike_range": 2,
        }
        timestamp = datetime(
            2025, 6, 9, 10, 30, tzinfo=ZoneInfo("America/New_York"),
        ).isoformat()
        rows = tuple({
            "symbol": "SPY", "expiration": "2025-07-18", "strike": 500.0,
            "right": right, "timestamp": timestamp, "bid": 3.0,
            "ask": 3.1, "bid_size": 5, "ask_size": 6,
        } for right in ("CALL", "PUT"))
        raw = _canonical_bytes(rows)
        return ThetaDataResponse(
            http_status=200, rows=rows, headers={},
            response_bytes=len(raw), elapsed_seconds=0.2,
            raw_body=raw, transport=TRANSPORT,
            library_version=TARGET_LIBRARY_VERSION,
            provider_environment_fingerprint="a" * 64,
            evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
        )

    report = canary.run_one_hourly_source_canary(
        settings, reader=reader, authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert report["provider_result"] == "OBSERVED_HOURLY_ROWS_SOURCE_DIAGNOSTIC"
    return settings, Path(report["report_path"])


def test_verified_preview_has_no_catalog_and_no_api(retained_source):
    settings, summary = retained_source
    record = hybrid.inspect_hourly_source(settings, summary)
    assert record["source_rows"] == 2
    assert record["source_status"] == "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
    assert record["query_coverage_proven"] is False
    assert record["simulator_ready"] is False
    assert record["provider_requests"] == 0
    assert not settings.resolved_path(hybrid.CATALOG_REL).exists()
    before = hybrid.inspect_exact_hourly_request(
        settings, symbol="SPY", date_et="2025-06-09", right="both",
    )
    assert before["status"] == "NOT_INDEXED"


def test_write_idempotent_and_safe_lookup(retained_source):
    settings, summary = retained_source
    first = hybrid.ingest_hourly_source(settings, summary)
    assert first["catalog_inserted"] is True
    assert first["catalog_observation_rows"] == 2
    assert first["source_rows"] == 2
    assert first["simulation_inputs_authorized"] is False
    db_path = settings.resolved_path(hybrid.CATALOG_REL)
    assert db_path.is_file()
    con = connect_utc(db_path, read_only=True)
    try:
        raw = con.execute(
            "SELECT source_status, query_coverage_proven, simulator_ready, "
            "source_rows FROM source_units",
        ).fetchall()
        observed = con.execute(
            "SELECT underlying, expiration, option_right FROM observed_quote_keys "
            "ORDER BY ordinal",
        ).fetchall()
    finally:
        con.close()
    assert raw == [("RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED", False, False, 2)]
    assert observed == [
        ("SPY", "2025-07-18", "CALL"),
        ("SPY", "2025-07-18", "PUT"),
    ]
    again = hybrid.ingest_hourly_source(settings, summary)
    assert again["catalog_inserted"] is False
    assert again["catalog_observation_rows"] == 2
    lookup = hybrid.inspect_exact_hourly_request(
        settings, symbol="SPY", date_et="2025-06-09", right="both",
    )
    assert lookup["source_present"] is True
    assert lookup["query_coverage_proven"] is False
    assert lookup["simulator_ready"] is False
    assert lookup["provider_requests"] == 0
    missing = hybrid.inspect_exact_hourly_request(
        settings, symbol="QQQ", date_et="2025-06-09", right="both",
    )
    assert missing["status"] == "NOT_INDEXED"


def test_modified_quote_raw_is_rejected_before_catalog_write(retained_source):
    settings, summary = retained_source
    report = json.loads(summary.read_text(encoding="utf-8"))
    receipt_path = Path(report["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    body = Path(receipt["body_path"])
    body.write_bytes(body.read_bytes() + b"x")
    with pytest.raises(hybrid.HybridCoverageError, match="SIZE_CHANGED"):
        hybrid.ingest_hourly_source(settings, summary)
    assert not settings.resolved_path(hybrid.CATALOG_REL).exists()


def test_modified_receipt_is_rejected_before_catalog_write(retained_source):
    settings, summary = retained_source
    report = json.loads(summary.read_text(encoding="utf-8"))
    receipt_path = Path(report["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["body_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(hybrid.HybridCoverageError, match="RECEIPT_IDENTITY"):
        hybrid.ingest_hourly_source(settings, summary)
    assert not settings.resolved_path(hybrid.CATALOG_REL).exists()


def test_cannot_register_external_or_unrelated_file(retained_source, tmp_path):
    settings, summary = retained_source
    fake = tmp_path / "outside" / "summary.json"
    fake.parent.mkdir()
    fake.write_bytes(summary.read_bytes())
    with pytest.raises(hybrid.HybridCoverageError, match="SOURCE_PATH_OUTSIDE"):
        hybrid.inspect_hourly_source(settings, fake)


def test_canary_is_not_promoted_even_if_summary_modified(retained_source):
    settings, summary = retained_source
    report = json.loads(summary.read_text(encoding="utf-8"))
    report["source_accepted"] = True
    summary.write_text(json.dumps(report))
    with pytest.raises(hybrid.HybridCoverageError, match="IDENTITY_OR_PROVENANCE"):
        hybrid.ingest_hourly_source(settings, summary)
    assert not settings.resolved_path(hybrid.CATALOG_REL).exists()


def test_cli_help_requires_no_database_or_provider():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "scripts.index_hybrid_options_coverage_v1",
         "--help"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--write-catalog" in result.stdout
