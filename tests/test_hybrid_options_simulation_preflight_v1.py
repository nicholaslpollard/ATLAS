from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from packages.data import thetadata_hourly_source_canary_v1 as canary
from packages.data import hybrid_options_simulation_preflight_v1 as preflight
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_coverage_catalog_v1 import (
    CATALOG_REL, ingest_hourly_source,
)
from packages.data.hybrid_options_gap_planner_v1 import demo_batch
from packages.data.hybrid_options_lossless_archive_v1 import archive_existing_source
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import preflight_hybrid_options_simulator_v1 as cli


class FakeSettings:
    def __init__(self, base: Path):
        self.base = base
        (base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, binding):
        assert binding == "options"

    def resolved_path(self, relative):
        return self.base / relative


@pytest.fixture(autouse=True)
def enough_synthetic_space(monkeypatch):
    class Disk:
        free = 200 * 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Disk())


@pytest.fixture
def archived_source(tmp_path):
    settings = FakeSettings(tmp_path)
    rows = tuple({
        "symbol": "SPY", "expiration": "2025-07-18",
        "strike": 500.0, "right": right,
        "timestamp": datetime(
            2025, 6, 9, 10, 30, tzinfo=ZoneInfo("America/New_York"),
        ).isoformat(),
        "bid": 3.0, "ask": 3.1, "bid_size": 5, "ask_size": 6,
    } for right in ("CALL", "PUT"))
    raw = _canonical_bytes(rows)

    def reader(**kwargs):
        assert kwargs["symbol"] == "SPY"
        return ThetaDataResponse(
            http_status=200, rows=rows, headers={},
            response_bytes=len(raw), elapsed_seconds=0.2,
            raw_body=raw, transport=TRANSPORT,
            library_version=TARGET_LIBRARY_VERSION,
            provider_environment_fingerprint="a" * 64,
            evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
        )

    canary_report = canary.run_one_hourly_source_canary(
        settings, reader=reader,
        authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    indexed = ingest_hourly_source(
        settings, Path(canary_report["report_path"]),
    )
    archive = archive_existing_source(
        settings, indexed["source_id"], write_archive=True,
    )
    return {
        "settings": settings,
        "source_id": indexed["source_id"],
        "archive": Path(archive["archive_path"]),
        "receipt": Path(archive["receipt_path"]),
    }


def test_preflight_verifies_archive_and_preserves_missing_gaps(archived_source):
    result = preflight.preflight_simulation_inputs(
        archived_source["settings"], demo_batch(),
    )
    assert result["contract"] == preflight.CONTRACT
    assert result["status"] == "SIMULATION_INPUTS_BLOCKED_SOURCE_ONLY"
    assert result["requirement_uses"] == 5
    assert result["unique_queries"] == 4
    assert result["deduplicated_uses"] == 1
    assert result["verified_archives"] == 1
    assert result["unqualified_observed_queries"] == 1
    assert result["missing_exact_queries"] == 3
    assert result["verified_archive_receipts"][0]["observed_quotes_verified"] == 2
    assert result["verified_archive_receipts"][0]["source_id"] == archived_source["source_id"]
    assert len([r for r in result["queries"] if
                r["readiness"] == "ARCHIVED_DIAGNOSTIC_NOT_EXECUTABLE"]) == 1
    assert result["simulator_run_permitted"] is False
    assert result["frozen_simulation_dataset_created"] is False
    assert result["automatic_acquisition_authorized"] is False
    assert result["provider_requests"] == 0
    assert result["broker_requests"] == 0
    assert result["protected_outcomes_read"] == 0
    assert result["simulations_run"] == 0
    assert result["uncompressed_original_sources_opened"] == 0
    assert result["report_fingerprint"] == _fingerprint({
        k: v for k, v in result.items() if k != "report_fingerprint"
    })
    assert preflight.preflight_simulation_inputs(
        archived_source["settings"], demo_batch(),
    ) == result


def test_reused_query_reads_archive_once(archived_source, monkeypatch):
    read = preflight.load_verified_archived_option_quotes
    called = []

    def counted(settings, source_id):
        called.append(source_id)
        return read(settings, source_id)

    monkeypatch.setattr(preflight, "load_verified_archived_option_quotes", counted)
    result = preflight.preflight_simulation_inputs(
        archived_source["settings"], demo_batch(),
    )
    assert result["deduplicated_uses"] == 1
    assert called == [archived_source["source_id"]]


def test_missing_catalog_never_creates_catalog_or_data(tmp_path):
    settings = FakeSettings(tmp_path)
    before = list(settings.resolved_path("data/options").iterdir())
    result = preflight.preflight_simulation_inputs(settings, demo_batch())
    assert result["verified_archives"] == 0
    assert result["missing_exact_queries"] == 4
    assert result["simulator_run_permitted"] is False
    assert list(settings.resolved_path("data/options").iterdir()) == before
    assert not settings.resolved_path(CATALOG_REL).exists()


@pytest.mark.parametrize("alteration", ["corrupt", "missing"])
def test_archive_integrity_failure_never_becomes_cache_miss(
    archived_source, alteration,
):
    archive = archived_source["archive"]
    if alteration == "corrupt":
        archive.write_bytes(archive.read_bytes() + b"tampered")
    else:
        archive.unlink()
    with pytest.raises(ValueError, match="ARCHIVE_"):
        preflight.preflight_simulation_inputs(
            archived_source["settings"], demo_batch(),
        )
    assert archived_source["settings"].resolved_path(CATALOG_REL).exists()


def test_receipt_tampering_refused(archived_source):
    receipt = archived_source["receipt"]
    obj = json.loads(receipt.read_text())
    obj["simulator_ready"] = True
    receipt.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="ARCHIVE_RECEIPT"):
        preflight.preflight_simulation_inputs(
            archived_source["settings"], demo_batch(),
        )


def test_catalog_authority_forgery_refused(archived_source):
    db = archived_source["settings"].resolved_path(CATALOG_REL)
    con = connect_utc(db)
    try:
        con.execute("UPDATE source_units SET simulator_ready=TRUE")
    finally:
        con.close()
    with pytest.raises(ValueError, match="ACCEPTANCE_STATE"):
        preflight.preflight_simulation_inputs(
            archived_source["settings"], demo_batch(),
        )


def test_preflight_never_promotes_even_forged_report(archived_source):
    report = preflight.preflight_simulation_inputs(
        archived_source["settings"], demo_batch(),
    )
    with pytest.raises(preflight.HybridSimulationPreflightError,
                       match="NOT_QUALIFIED"):
        preflight.require_qualified_simulation_inputs(report)
    fake = dict(report)
    fake.update(
        simulator_run_permitted=True,
        all_required_sources_qualified=True,
        frozen_simulation_dataset_created=True,
    )
    fake["report_fingerprint"] = _fingerprint({
        k: v for k, v in fake.items() if k != "report_fingerprint"
    })
    with pytest.raises(preflight.HybridSimulationPreflightError,
                       match="NO_SIMULATOR_PROMOTION_AUTHORITY"):
        preflight.require_qualified_simulation_inputs(fake)


def test_enforce_ready_exits_nonzero_but_normal_audit_succeeds(
    archived_source, monkeypatch, capsys,
):
    monkeypatch.setattr(cli, "load_settings", lambda *a: archived_source["settings"])
    assert cli.main(["--demo"]) == 0
    result = capsys.readouterr().out
    assert "verified_archives=1" in result
    assert "simulator_run_permitted=False" in result
    assert cli.main(["--demo", "--require-ready"]) == 4
    result = capsys.readouterr().out
    assert "BLOCKED: SIMULATION_INPUTS_NOT_QUALIFIED" in result
    assert "provider fallback" in result


def test_cli_help_no_credentials_or_provider():
    process = subprocess.run(
        [sys.executable, "-m", "scripts.preflight_hybrid_options_simulator_v1",
         "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True, capture_output=True, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    assert "--requirements" in process.stdout
    assert "--require-ready" in process.stdout


def test_source_query_identity_drift_is_blocked(archived_source, monkeypatch):
    read = preflight.load_verified_archived_option_quotes

    def changed_scope(settings, source_id):
        info = dict(read(settings, source_id))
        info["query_scope"] = {**info["query_scope"], "symbol": "QQQ"}
        return info

    monkeypatch.setattr(preflight, "load_verified_archived_option_quotes", changed_scope)
    with pytest.raises(preflight.HybridSimulationPreflightError,
                       match="IDENTITY_OR_AUTHORITY_DRIFT"):
        preflight.preflight_simulation_inputs(
            archived_source["settings"], demo_batch(),
        )
