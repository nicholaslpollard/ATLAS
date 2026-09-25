from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest

from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data import marketdata_accepted_stock_candidate_export_v1 as exporter


ROOT = Path(__file__).resolve().parents[1]


def _parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)  # isolated test fixture rewrite only
    connection = duckdb.connect()
    try:
        connection.register("source_rows", frame)
        connection.execute("COPY source_rows TO '" + path.as_posix().replace("'", "''") + "' (FORMAT PARQUET)")
    finally:
        connection.close()


def test_raw_native_open_not_split_adjusted_open(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    settings = load_settings(ROOT, "development").model_copy(update={"project_root": project})
    monkeypatch.setattr(exporter, "load_settings", lambda *_a, **_kw: settings)
    layout = V2Layout.beneath((project / "data").resolve())
    session = date(2025, 9, 16)
    item = SimpleNamespace(
        opportunity_id="accepted-1", instrument_id="inst-1",
        ticker="SPY", signal_session=date(2025, 9, 15),
        entry_utc=exporter.get_market_calendar().regular_open_close(session)[0],
    )

    research = tmp_path / "accepted-research.parquet"
    _parquet(research, pd.DataFrame([{
        "instrument_id": "inst-1", "ticker": "SPY",
        "session_date": session, "open": 200.0,
        "unadjusted_close": 110.0, "price_adjustment_mode": "SPLIT_ADJUSTED",
    }]))
    monkeypatch.setattr(
        exporter, "_validated_daily_source",
        lambda *_args: (
            "read_parquet('" + str(research).replace("\\", "/") + "', hive_partitioning=false)",
            {"source_fingerprint": "a" * 64, "protected_master_return_rows_read": 0},
        ),
    )
    unit_id = "b" * 64
    partition = Path("year=2025") / "batch=0001"
    canonical = layout.canonical_daily / partition / f"{unit_id[:20]}.parquet"
    def create_native(closing: float) -> None:
        _parquet(canonical, pd.DataFrame([{
            "symbol": "SPY", "session_date": session,
            "open": 100.0, "close": closing,
            "provider": "alpaca", "dataset": "stock_daily_aggregates",
            "timeframe": "1d", "session_segment": "regular",
            "is_adjusted": False,
            "source_id": f"alpaca:sip:1Day:raw:asof=-:v2:unit={unit_id}",
        }]))
        checkpoint = layout.checkpoints / "native_units" / "1d" / partition / f"{unit_id[:20]}.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps({
            "contract": exporter.UNIT_CONTRACT, "status": "COMPLETE",
            "unit_id": unit_id, "policy_sha256": "c" * 64,
            "universe_sha256": "d" * 64,
            "canonical": {
                "path": str(canonical.absolute()),
                "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
            },
            "provider_rejections": [],
        }))
    record = {
        "unit_id": unit_id, "year": 2025, "batch_index": 1,
        "symbols": ["SPY"], "policy_sha256": "c" * 64,
        "universe_sha256": "d" * 64,
    }
    monkeypatch.setattr(
        exporter, "_accepted_native_plan",
        lambda *_args: (
            [record], {"native_acceptance_fingerprint": "e" * 64}, layout,
        ),
    )
    create_native(110.0)
    prices, report = exporter._read_entry_opens(project, (item,))
    assert prices == {"accepted-1": 100.0}
    assert report["native_raw_source"]["verified_native_raw_unit_count"] == 1

    create_native(111.0)
    with pytest.raises(exporter.CandidateStockExportError, match="raw close disagrees"):
        exporter._read_entry_opens(project, (item,))
