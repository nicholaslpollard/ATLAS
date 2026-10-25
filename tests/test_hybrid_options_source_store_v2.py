from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import pytest

from packages.data import hybrid_options_source_store_v2 as v6
from packages.data import thetadata_hourly_source_canary_v1 as canary
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_archive_reader_v1 import (
    load_verified_archived_option_quotes,
)
from packages.data.hybrid_options_coverage_catalog_v1 import ingest_hourly_source
from packages.data.hybrid_options_lossless_archive_v1 import archive_existing_source
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import index_hybrid_options_general_source_v2 as cli


class FakeSettings:
    def __init__(self, base: Path):
        self.base = base
        (self.base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, binding):
        assert binding == "options"

    def resolved_path(self, relative):
        return self.base / relative


@pytest.fixture(autouse=True)
def disk_headroom(monkeypatch):
    class Disk:
        free = 200 * 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _: Disk())


def query(symbol="SPY", day="2025-06-09", interval="1h"):
    return {
        "symbol": symbol, "date_et": day, "expiration": "*",
        "right": "both", "interval": interval, "start_time": "09:30:00",
        "end_time": "16:00:00", "max_dte": 45, "strike_range": 2,
    }


def synthetic_rows(symbol="SPY", day="2025-06-09", *, bid=3.0):
    return tuple({
        "symbol": symbol, "expiration": "2025-07-18",
        "strike": 500.0, "right": right,
        "timestamp": datetime.fromisoformat(
            day + "T10:30:00"
        ).replace(tzinfo=ZoneInfo("America/New_York")).isoformat(),
        "bid": bid, "ask": 3.5, "bid_size": 5, "ask_size": 6,
    } for right in ("CALL", "PUT"))


def sdk_response(rows, *, version=TARGET_LIBRARY_VERSION):
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=tuple(rows), headers={},
        raw_body=raw, response_bytes=len(raw),
        elapsed_seconds=0.15, transport=TRANSPORT,
        library_version=version,
        provider_environment_fingerprint="a" * 64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )


@pytest.fixture
def settings(tmp_path):
    return FakeSettings(tmp_path)


def test_preview_is_no_write_and_supports_general_query(settings):
    before = list(settings.resolved_path("data/options").iterdir())
    result = v6.store_historical_quote_source(
        settings, query("QQQ", "2024-03-04", "1m"),
        response=sdk_response(synthetic_rows("QQQ", "2024-03-04")),
    )
    assert result["diagnostics"]["observed_rows"] == 2
    assert result["diagnostics"]["distinct_contracts"] == 2
    assert result["compressed_bytes"] > 0
    assert result["archived"] is False
    assert result["simulator_ready"] is False
    assert list(settings.resolved_path("data/options").iterdir()) == before


def test_gzip_at_ingestion_idempotence_and_verified_index(settings):
    request = query()
    response = sdk_response(synthetic_rows())
    first = v6.store_historical_quote_source(
        settings, request, response=response, write=True,
    )
    assert first["new_archive"] is True
    assert first["new_catalog_entry"] is True
    assert first["provenance"]["origin"] == "THETADATA_ISOLATED_SDK"
    assert first["simulator_ready"] is False
    reader = v6.read_historical_quote_source(settings, first["source_id"])
    assert reader["quote_rows"] == 2
    assert reader["query"] == request
    assert reader["simulator_ready"] is False
    assert reader["query_coverage_proven"] is False
    assert reader["provider_requests"] == 0
    again = v6.store_historical_quote_source(
        settings, request, response=response, write=True,
    )
    assert again["new_archive"] is False
    assert again["new_catalog_entry"] is False
    assert again["source_id"] == first["source_id"]
    con = connect_utc(settings.resolved_path(v6.CATALOG_REL), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM quote_sources").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM quote_keys").fetchone()[0] == 2
    finally:
        con.close()


def test_multiple_symbols_and_resolutions_have_separate_keys(settings):
    for symbol, day, interval in [
        ("SPY", "2025-06-09", "1h"),
        ("QQQ", "2025-06-09", "1h"),
        ("SPY", "2024-03-04", "1m"),
    ]:
        receipt = v6.store_historical_quote_source(
            settings, query(symbol, day, interval),
            response=sdk_response(synthetic_rows(symbol, day)),
            write=True,
        )
        assert v6.read_historical_quote_source(
            settings, receipt["source_id"],
        )["quote_rows"] == 2
    con = connect_utc(settings.resolved_path(v6.CATALOG_REL), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM quote_sources").fetchone()[0] == 3
        assert con.execute("SELECT COUNT(*) FROM quote_keys").fetchone()[0] == 6
    finally:
        con.close()


def test_same_query_different_provider_bytes_refused(settings):
    v6.store_historical_quote_source(
        settings, query(), response=sdk_response(synthetic_rows()), write=True,
    )
    with pytest.raises(v6.HybridSourceStoreError, match="DIFFERENT_IMMUTABLE_SOURCE"):
        v6.store_historical_quote_source(
            settings, query(),
            response=sdk_response(synthetic_rows(bid=2.0)), write=True,
        )


@pytest.mark.parametrize("tamper", ["gzip", "receipt", "catalog", "key"])
def test_tampering_fails_closed(settings, tamper):
    report = v6.store_historical_quote_source(
        settings, query(), response=sdk_response(synthetic_rows()), write=True,
    )
    source_id = report["source_id"]
    archived, proof = v6._paths(settings, source_id)
    if tamper == "gzip":
        archived.write_bytes(archived.read_bytes() + b"bad")
    elif tamper == "receipt":
        original = json.loads(proof.read_bytes())
        original["simulator_ready"] = True
        proof.write_text(json.dumps(original))
    else:
        con = connect_utc(settings.resolved_path(v6.CATALOG_REL))
        try:
            if tamper == "catalog":
                con.execute(
                    "UPDATE quote_sources SET simulator_ready=TRUE "
                    "WHERE source_id=?", [source_id],
                )
            else:
                con.execute(
                    "UPDATE quote_keys SET option_right='PUT' "
                    "WHERE source_id=? AND ordinal=0", [source_id],
                )
        finally:
            con.close()
    with pytest.raises(ValueError):
        v6.read_historical_quote_source(settings, source_id)


def test_outside_dte_preserved_as_diagnostic_not_dropped(settings):
    rows = list(synthetic_rows())
    rows[0] = {**rows[0], "expiration": "2026-07-18"}
    indexed = v6.store_historical_quote_source(
        settings, query(), response=sdk_response(rows), write=True,
    )
    assert indexed["diagnostics"]["outside_requested_dte"] == 1
    assert indexed["diagnostics"]["observed_rows"] == 2
    assert v6.read_historical_quote_source(
        settings, indexed["source_id"],
    )["diagnostics"]["outside_requested_dte"] == 1


def test_crossed_book_retained_but_unqualified(settings):
    rows = list(synthetic_rows())
    rows[0] = {**rows[0], "bid": 10.0, "ask": 2.0}
    receipt = v6.store_historical_quote_source(
        settings, query(), response=sdk_response(rows), write=True,
    )
    assert receipt["diagnostics"]["crossed_bid_ask"] == 1
    assert receipt["simulator_ready"] is False


def test_invalid_sdk_metadata_no_source_write(settings):
    with pytest.raises(v6.HybridSourceStoreError, match="PROVIDER_SOURCE_ENVELOPE"):
        v6.store_historical_quote_source(
            settings, query(),
            response=sdk_response(synthetic_rows(), version="fake"),
            write=True,
        )
    assert not settings.resolved_path(v6.CATALOG_REL).exists()


def test_wrong_symbol_and_unaware_clock_rejected(settings):
    with pytest.raises(v6.HybridSourceStoreError, match="ROW_IDENTITY"):
        v6.store_historical_quote_source(
            settings, query("SPY"),
            response=sdk_response(synthetic_rows("QQQ")),
        )
    rows = list(synthetic_rows())
    rows[0] = {**rows[0], "timestamp": "2025-06-09T10:30:00"}
    with pytest.raises(v6.HybridSourceStoreError, match="ROW_IDENTITY"):
        v6.store_historical_quote_source(
            settings, query(), response=sdk_response(rows),
        )


def test_reject_invalid_query_and_empty_rows(settings):
    invalid = {**query(), "interval": "10s"}
    with pytest.raises(v6.HybridSourceStoreError, match="INVALID_EXACT"):
        v6.store_historical_quote_source(
            settings, invalid, response=sdk_response(synthetic_rows()),
        )
    with pytest.raises(v6.HybridSourceStoreError, match="CANONICAL_ROWS"):
        v6.store_historical_quote_source(
            settings, query(), response=sdk_response(tuple()),
        )


def test_v4_verified_archive_can_bootstrap_v6_without_provider(settings, monkeypatch, capsys):
    rows = synthetic_rows()
    response = sdk_response(rows)

    def fake_read(**kwargs):
        assert kwargs["symbol"] == "SPY"
        return response

    old = canary.run_one_hourly_source_canary(
        settings, reader=fake_read, authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    initial = ingest_hourly_source(
        settings, Path(old["report_path"]),
    )
    archived = archive_existing_source(
        settings, initial["source_id"], write_archive=True,
    )
    assert archived["archive_inserted"] is True
    known = load_verified_archived_option_quotes(
        settings, initial["source_id"],
    )
    dry = v6.store_historical_quote_source(
        settings, known["query_scope"], verified_v4=known,
    )
    assert dry["provenance"]["origin"] == "VERIFIED_EXISTING_V4_ARCHIVE"
    record = v6.store_historical_quote_source(
        settings, known["query_scope"], verified_v4=known, write=True,
    )
    assert v6.read_historical_quote_source(
        settings, record["source_id"],
    )["quote_rows"] == 2
    # V1 catalog and immutable source remain unchanged and re-readable.
    assert load_verified_archived_option_quotes(
        settings, initial["source_id"],
    )["quote_rows"] == 2
    monkeypatch.setattr(cli, "load_settings", lambda *args: settings)
    monkeypatch.setattr(cli, "SPY_V4_ID", initial["source_id"])
    assert cli.main([]) == 0
    assert "archived=False" in capsys.readouterr().out
    assert cli.main(["--import-verified-v4"]) == 0
    assert "reverified_from=V6_VERIFIED_GZIP" in capsys.readouterr().out
    assert cli.main(["--check-source", record["source_id"]]) == 0
    assert "simulator_ready=False" in capsys.readouterr().out
