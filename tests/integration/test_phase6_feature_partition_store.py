from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("duckdb")

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import FeaturePartitionStore


def make_settings(tmp_path: Path):
    settings = load_settings()
    settings.project_root = tmp_path
    return settings


def write_source(path: Path, *, close: float = 101.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "symbol": ["TPC", "TpC"],
            "timestamp_utc": [
                datetime(2026, 8, 14, 13, 30, tzinfo=UTC),
                datetime(2026, 8, 14, 13, 30, tzinfo=UTC),
            ],
            "high": [102.0, 12.0],
            "low": [99.0, 9.0],
            "close": [close, 11.0],
            "volume": [1000.0, 500.0],
        }
    )
    con = connect_utc(":memory:")
    try:
        con.register("source_frame", frame)
        con.execute(
            f"COPY source_frame TO {sql_string(path)} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()


def test_feature_partition_manifest_tracks_source_and_incoming_state(tmp_path):
    settings = make_settings(tmp_path)
    store = FeaturePartitionStore(settings)
    d = date(2026, 8, 14)
    timeframe = Timeframe.HOUR_4
    source = store.source_path(timeframe, d)
    write_source(source)

    feature_frame = pd.DataFrame(
        {
            "symbol": ["TPC", "TpC"],
            "timestamp_utc": [
                datetime(2026, 8, 14, 13, 30, tzinfo=UTC),
                datetime(2026, 8, 14, 13, 30, tzinfo=UTC),
            ],
            "ema_20": [100.5, 10.5],
        }
    )
    record = store.write(
        feature_frame,
        timeframe=timeframe,
        trading_date=d,
        input_state_fingerprint="state-before",
        output_state_fingerprint="state-after",
    )

    assert record.row_count == 2
    assert record.symbol_count == 2
    assert store.is_current(
        timeframe,
        d,
        input_state_fingerprint="state-before",
    )
    assert not store.is_current(
        timeframe,
        d,
        input_state_fingerprint="different-prior-state",
    )

    # A corrected source partition invalidates the feature partition even when the
    # feature file itself and incoming recursive state are unchanged.
    write_source(source, close=100.5)
    assert not store.is_current(
        timeframe,
        d,
        input_state_fingerprint="state-before",
    )
