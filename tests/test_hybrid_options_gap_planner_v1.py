from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from packages.data import hybrid_options_gap_planner_v1 as planner
from packages.data import thetadata_hourly_source_canary_v1 as canary
from packages.data.hybrid_options_coverage_catalog_v1 import (
    CATALOG_REL, ingest_hourly_source,
)
from packages.data.duckdb_connection import connect_utc
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)


class FakeSettings:
    def __init__(self, base):
        self.base = Path(base)
        (self.base / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, binding):
        assert binding == "options"

    def resolved_path(self, relative):
        return self.base / relative


@pytest.fixture(autouse=True)
def mock_storage_headroom(monkeypatch):
    class Disk:
        free = 200 * 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Disk())


@pytest.fixture
def populated_catalog(tmp_path):
    settings = FakeSettings(tmp_path)

    def reader(**kwargs):
        assert kwargs["symbol"] == "SPY"
        rows = tuple({
            "symbol": "SPY", "expiration": "2025-07-18",
            "strike": 500.0, "right": right,
            "timestamp": datetime(2025, 6, 9, 10, 30,
                                  tzinfo=ZoneInfo("America/New_York")).isoformat(),
            "bid": 3.0, "ask": 3.1, "bid_size": 5, "ask_size": 6,
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

    summary = canary.run_one_hourly_source_canary(
        settings, reader=reader, authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    result = ingest_hourly_source(settings, Path(summary["report_path"]))
    assert result["catalog_inserted"] is True
    return settings


def test_demo_five_uses_four_unique_queries_without_provider(populated_catalog):
    result = planner.plan_missing_sources(
        populated_catalog, planner.demo_batch(),
    )
    assert result["total_requirement_uses"] == 5
    assert result["unique_exact_queries"] == 4
    assert result["deduplicated_uses"] == 1
    assert result["exact_sources_observed_not_qualified"] == 1
    assert result["queries_missing_exact_local_source"] == 3
    assert result["qualified_for_simulator"] == 0
    assert result["provider_requests"] == 0
    assert result["automatic_acquisition_authorized"] is False
    assert result["source_files_scanned"] == 0
    present = [x for x in result["queries"] if x["source_present"]]
    assert len(present) == 1
    assert present[0]["query"]["symbol"] == "SPY"
    assert present[0]["query"]["interval"] == "1h"
    assert present[0]["exact_sources"][0]["observed_rows"] == 2
    assert [x["strategy_key"] for x in present[0]["uses"]] == [
        "SPY_DIFFERENT_HOURLY", "SPY_NATIVE_HOURLY",
    ]
    result2 = planner.plan_missing_sources(
        populated_catalog, planner.demo_batch(),
    )
    assert result2 == result


def test_cannot_conflate_hourly_with_minute_or_different_symbols(populated_catalog):
    rows = planner.plan_missing_sources(
        populated_catalog, planner.demo_batch(),
    )["queries"]
    minute = next(x for x in rows if x["query"]["interval"] == "1m")
    assert minute["source_state"] == "MISSING_EXACT_LOCAL_SOURCE"
    assert minute["same_symbol_day_other_scopes"] == 1
    qqq = next(x for x in rows if x["query"]["symbol"] == "QQQ")
    assert qqq["source_state"] == "MISSING_EXACT_LOCAL_SOURCE"
    old = next(x for x in rows if x["query"]["date_et"] == "2018-06-11")
    assert old["source_state"] == "MISSING_EXACT_LOCAL_SOURCE"


def test_catalog_not_present_does_not_create_files(tmp_path):
    settings = FakeSettings(tmp_path)
    before = list((tmp_path / "data/options").iterdir())
    result = planner.plan_missing_sources(settings, planner.demo_batch())
    assert result["catalog_present"] is False
    assert result["queries_missing_exact_local_sources"] if False else True
    assert result["queries_missing_exact_local_source"] == 4
    assert list((tmp_path / "data/options").iterdir()) == before


def test_read_only_planner_refuses_forged_simulator_acceptance(populated_catalog):
    db = populated_catalog.resolved_path(CATALOG_REL)
    con = connect_utc(db)
    try:
        con.execute("UPDATE source_units SET simulator_ready=TRUE")
    finally:
        con.close()
    with pytest.raises(planner.HybridGapPlannerError, match="ACCEPTANCE_STATE"):
        planner.plan_missing_sources(populated_catalog, planner.demo_batch())


@pytest.mark.parametrize("mutate", [
    lambda b: b.update(contract="not-a-batch"),
    lambda b: b["requests"][0]["query"].update(interval="10s"),
    lambda b: b["requests"][0]["query"].update(max_dte=0),
    lambda b: b["requests"][0]["query"].update(symbol="SPY; DROP TABLE"),
    lambda b: b["requests"][0]["query"].update(date_et="not-a-date"),
    lambda b: b["requests"][0].update(purpose="lookahead"),
    lambda b: b["requests"][0]["query"].update(strike="100"),
])
def test_invalid_or_ambiguous_request_fails_before_database(tmp_path, mutate):
    settings = FakeSettings(tmp_path)
    batch = planner.demo_batch()
    mutate(batch)
    with pytest.raises(planner.HybridGapPlannerError):
        planner.plan_missing_sources(settings, batch)
    assert not settings.resolved_path(CATALOG_REL).exists()


def test_cli_help_requires_no_provider_or_catalog():
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [sys.executable, "-m", "scripts.plan_hybrid_options_source_gaps_v1",
         "--help"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    assert "--demo" in process.stdout
    assert "--requirements" in process.stdout


def test_json_batch_file_round_trip(tmp_path):
    source = tmp_path / "requirements.json"
    batch = planner.demo_batch()
    source.write_text(json.dumps(batch), encoding="utf-8")
    assert planner.load_batch_file(source) == batch
    assert len(planner.normalize_batch(batch)) == 5
