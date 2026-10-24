from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import pytest

from packages.data import thetadata_hourly_source_canary_v1 as canary
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_archive_reader_v1 import (
    HybridArchiveReaderError, load_verified_archived_option_quotes,
)
from packages.data.hybrid_options_coverage_catalog_v1 import (
    CATALOG_REL, ingest_hourly_source,
)
from packages.data.hybrid_options_lossless_archive_v1 import (
    archive_existing_source,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)


class FakeSettings:
    def __init__(self, base: Path):
        self.base = base
        (base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, binding: str):
        assert binding == "options"

    def resolved_path(self, relative: str):
        return self.base / relative


@pytest.fixture(autouse=True)
def synthetic_free_space(monkeypatch):
    class Disk:
        free = 200 * 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Disk())


@pytest.fixture
def source_archive(tmp_path):
    settings = FakeSettings(tmp_path)
    rows = tuple({
        "symbol": "SPY",
        "expiration": "2025-07-18",
        "strike": 500.0,
        "right": right,
        "timestamp": datetime(
            2025, 6, 9, 10, 30,
            tzinfo=ZoneInfo("America/New_York"),
        ).isoformat(),
        "bid": 3.0,
        "ask": 3.1,
        "bid_size": 5,
        "ask_size": 6,
    } for right in ("CALL", "PUT"))
    raw = _canonical_bytes(rows)

    def reader(**kwargs):
        assert kwargs["symbol"] == "SPY"
        return ThetaDataResponse(
            http_status=200, rows=rows, headers={}, response_bytes=len(raw),
            elapsed_seconds=0.2, raw_body=raw, transport=TRANSPORT,
            library_version=TARGET_LIBRARY_VERSION,
            provider_environment_fingerprint="a" * 64,
            evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
        )

    source_receipt = canary.run_one_hourly_source_canary(
        settings, reader=reader,
        authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    registered = ingest_hourly_source(
        settings, Path(source_receipt["report_path"]),
    )
    archived = archive_existing_source(
        settings, registered["source_id"], write_archive=True,
    )
    assert archived["archive_inserted"] is True
    return {
        "settings": settings,
        "source_id": registered["source_id"],
        "rows": rows,
        "archive": Path(archived["archive_path"]),
        "receipt": Path(archived["receipt_path"]),
        "original": Path(json.loads(
            Path(source_receipt["receipt_path"]).read_text(),
        )["body_path"]),
    }


def test_reads_exact_original_observations_from_archive(source_archive):
    item = source_archive
    result = load_verified_archived_option_quotes(
        item["settings"], item["source_id"],
    )
    assert result["rows"] == item["rows"]
    assert result["quote_rows"] == 2
    assert result["unique_contracts"] == 2
    assert result["rights_observed"] == {"CALL": 1, "PUT": 1}
    assert result["interval"] == "1h"
    assert result["symbol"] == "SPY"
    assert result["session_et"] == "2025-06-09"
    assert result["source_id"] == item["source_id"]
    assert result["source_status"] == "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
    assert result["simulator_ready"] is False
    assert result["query_coverage_proven"] is False
    assert result["original_uncompressed_source_opened"] is False
    assert result["provider_requests"] == 0
    assert result["protected_outcomes_read"] == 0


def test_read_succeeds_using_archive_without_original_json_file(source_archive):
    item = source_archive
    # Only synthetic test files are altered; production originals remain intact.
    item["original"].unlink()
    assert not item["original"].exists()
    result = load_verified_archived_option_quotes(
        item["settings"], item["source_id"],
    )
    assert result["rows"] == item["rows"]
    assert result["retrieved_from"] == "VERIFIED_LOCAL_COMPRESSED_ARCHIVE"


def test_archive_corruption_blocks_read_without_provider_fallback(source_archive):
    item = source_archive
    item["archive"].write_bytes(item["archive"].read_bytes() + b"tampered")
    with pytest.raises(HybridArchiveReaderError, match="ARCHIVE_RECEIPT"):
        load_verified_archived_option_quotes(item["settings"], item["source_id"])


def test_archive_receipt_tampering_blocks_read(source_archive):
    item = source_archive
    doc = json.loads(item["receipt"].read_text())
    doc["simulator_ready"] = True
    item["receipt"].write_text(json.dumps(doc))
    with pytest.raises(HybridArchiveReaderError, match="ARCHIVE_RECEIPT"):
        load_verified_archived_option_quotes(item["settings"], item["source_id"])


def test_catalog_observation_key_change_blocks_read(source_archive):
    item = source_archive
    db = item["settings"].resolved_path(CATALOG_REL)
    con = connect_utc(db)
    try:
        con.execute(
            "UPDATE observed_quote_keys SET option_right='PUT' "
            "WHERE source_id=? AND ordinal=0",
            [item["source_id"]],
        )
    finally:
        con.close()
    with pytest.raises(HybridArchiveReaderError, match="CATALOG_KEY_DRIFT"):
        load_verified_archived_option_quotes(item["settings"], item["source_id"])


def test_catalog_authority_forgery_blocks_read(source_archive):
    item = source_archive
    db = item["settings"].resolved_path(CATALOG_REL)
    con = connect_utc(db)
    try:
        con.execute(
            "UPDATE source_units SET simulator_ready=TRUE WHERE source_id=?",
            [item["source_id"]],
        )
    finally:
        con.close()
    with pytest.raises(HybridArchiveReaderError, match="STATUS_INVALID"):
        load_verified_archived_option_quotes(item["settings"], item["source_id"])


@pytest.mark.parametrize("wrong", ["", "../oops", "a" * 63, "g" * 64])
def test_invalid_ids_never_open_provider(source_archive, wrong):
    with pytest.raises(HybridArchiveReaderError, match="INVALID_EXACT_SOURCE_ID"):
        load_verified_archived_option_quotes(source_archive["settings"], wrong)


def test_missing_exact_archive_refuses_source_fallback(source_archive):
    item = source_archive
    item["archive"].unlink()
    with pytest.raises(HybridArchiveReaderError, match="ARCHIVE_PATH_UNAVAILABLE"):
        load_verified_archived_option_quotes(item["settings"], item["source_id"])
    assert item["original"].is_file()
