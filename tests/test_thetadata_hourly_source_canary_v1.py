from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from packages.data import thetadata_hourly_source_canary_v1 as hourly
from packages.data.thetadata_hourly_source_canary_v1 import (
    HourlySourceCanaryError, design, run_one_hourly_source_canary,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataError, ThetaDataResponse, _canonical_bytes,
)


@pytest.fixture(autouse=True)
def fake_disk_capacity(monkeypatch):
    # GitHub-hosted test runners can be smaller than the workstation D: volume.
    class Disk:
        free = 200 * 1024**3
    monkeypatch.setattr(hourly.shutil, "disk_usage", lambda _path: Disk())


class FakeSettings:
    def __init__(self, base: Path):
        self.base = base
        (base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, category):
        assert category == "options"

    def resolved_path(self, relative):
        return self.base / relative


def response_for(expirations=("2025-07-18",)):
    rows = tuple({
        "symbol": "SPY",
        "expiration": exp,
        "strike": 500.0,
        "right": right,
        "timestamp": datetime(2025, 6, 9, 10, 30,
                              tzinfo=ZoneInfo("America/New_York")).isoformat(),
        "bid": 3.0, "ask": 3.1, "bid_size": 5, "ask_size": 7,
    } for exp in expirations for right in ("CALL", "PUT"))
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={}, response_bytes=len(raw),
        elapsed_seconds=0.3, raw_body=raw, transport=TRANSPORT,
        library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="a" * 64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )


def test_frozen_scope_and_zero_read_default():
    plan = design()
    assert plan["scope"]["interval"] == "1h"
    assert plan["scope"]["symbol"] == "SPY"
    assert plan["scope"]["date_et"] == "2025-06-09"
    assert plan["method_cap"] == 1
    assert plan["provider_requests"] == 0
    assert plan["source_accepted"] is False


@pytest.mark.parametrize("flags", [
    {},
    {"authorize_one_hourly_quote": True},
    {"confirm_thetadata_standard": True},
    {"acknowledge_one_quote_method_call": True},
    {"authorize_one_hourly_quote": True, "confirm_thetadata_standard": True},
    {"authorize_one_hourly_quote": True,
     "acknowledge_one_quote_method_call": True},
    {"confirm_thetadata_standard": True,
     "acknowledge_one_quote_method_call": True},
])
def test_requires_all_three_flags_without_any_disk_or_provider_activity(tmp_path, flags):
    seen = []
    settings = FakeSettings(tmp_path)
    with pytest.raises(HourlySourceCanaryError, match="NOT_AUTHORIZED"):
        run_one_hourly_source_canary(
            settings, reader=lambda **kwargs: seen.append(kwargs), **flags,
        )
    assert seen == []
    assert list((tmp_path / "data/options").iterdir()) == []


def test_one_request_retains_original_rows_and_gzip_measurement(tmp_path):
    seen = []

    def reader(**kwargs):
        seen.append(kwargs)
        return response_for(("2025-07-18", "2025-08-15"))

    report = run_one_hourly_source_canary(
        FakeSettings(tmp_path), reader=reader,
        authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert len(seen) == 1
    assert seen[0] == {
        "symbol": "SPY", "date_et": "2025-06-09",
        "right": "both", "max_dte": 45, "strike_range": 2,
    }
    assert report["provider_result"] == "OBSERVED_HOURLY_DTE_SCOPE_DISCREPANCY"
    diag = report["source_diagnostics"]
    assert diag["rows"] == 4
    assert diag["rights"] == {"CALL": 2, "PUT": 2}
    assert diag["out_of_requested_dte_rows"] == 2
    assert diag["source_accepted"] is False
    assert report["source_accepted"] is False
    assert report["requests_attempted"] == 1
    assert report["gzip_9_size_bytes"] > 0
    assert report["gzip_9_size_bytes"] < report["source_bytes"]
    assert report["historical_replay_authority"] is False
    saved = json.loads(Path(report["report_path"]).read_text())
    receipt = json.loads(Path(saved["receipt_path"]).read_text())
    raw = Path(receipt["body_path"]).read_bytes()
    assert len(json.loads(raw)) == 4
    assert receipt["body_sha256"] == report["sdk_normalized_sha256"]
    assert (Path(report["report_path"]).parent / "attempt.json").exists()


def test_transport_failure_remains_one_attempt_and_does_not_leak_exception(tmp_path):
    seen = []

    def reader(**kwargs):
        seen.append(kwargs)
        raise ThetaDataError("do-not-print-sensitive-data", http_status=403)

    report = run_one_hourly_source_canary(
        FakeSettings(tmp_path), reader=reader,
        authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert len(seen) == 1
    assert report["provider_result"] == "METHOD_TRANSPORT_OR_ENTITLEMENT_ERROR"
    assert report["sdk_normalized_response_retained"] is False
    assert "do-not-print-sensitive-data" not in Path(report["report_path"]).read_text()


def test_cli_default_and_partial_flags_cannot_construct_sdk():
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "scripts.probe_thetadata_spy_hourly_source_v1"]
    output = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30)
    assert output.returncode == 0, output.stderr
    assert "ONE_HOURLY_ANCHOR_DESIGN_ZERO_REQUESTS" in output.stdout
    stop = subprocess.run(
        [*cmd, "--authorize-one-hourly-quote"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert stop.returncode == 2
    assert "BLOCKED_PARTIAL_HOURLY_AUTHORIZATION" in stop.stdout
