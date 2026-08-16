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
from packages.features.historical_materializer import (
    FeatureBootstrapRequired,
    HistoricalFeatureMaterializer,
)


def make_settings(tmp_path: Path):
    settings = load_settings()
    settings.project_root = tmp_path
    return settings


def write_4h_source(materializer: HistoricalFeatureMaterializer, d: date, offset: float) -> None:
    path = materializer.partition_store.source_path(Timeframe.HOUR_4, d)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "symbol": ["TPC", "TpC"],
            "timestamp_utc": [
                datetime(d.year, d.month, d.day, 13, 30, tzinfo=UTC),
                datetime(d.year, d.month, d.day, 13, 30, tzinfo=UTC),
            ],
            "high": [102.0 + offset, 12.0 + offset],
            "low": [99.0 + offset, 9.0 + offset],
            "close": [101.0 + offset, 11.0 + offset],
            "volume": [1000.0 + offset, 500.0 + offset],
        }
    )
    con = connect_utc(":memory:")
    try:
        con.register("bars", frame)
        con.execute(f"COPY bars TO {sql_string(path)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()


def test_historical_materializer_requires_explicit_genesis_bootstrap(tmp_path):
    service = HistoricalFeatureMaterializer(make_settings(tmp_path))
    d = date(2026, 8, 13)
    write_4h_source(service, d, 0.0)
    with pytest.raises(FeatureBootstrapRequired):
        service.materialize_range(timeframe=Timeframe.HOUR_4, start=d, end=d)


def test_historical_materializer_checkpoints_and_resumes_without_case_folding(tmp_path):
    service = HistoricalFeatureMaterializer(make_settings(tmp_path))
    first = date(2026, 8, 13)
    second = date(2026, 8, 14)
    write_4h_source(service, first, 0.0)
    write_4h_source(service, second, 1.0)

    result = service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=first,
        end=second,
        bootstrap_from_empty=True,
    )
    assert result.sessions_processed == 2
    assert result.rows_processed == 4
    assert result.checkpoint_as_of == second

    current = service.paths.feature_current_state_file(Timeframe.HOUR_4)
    engine, payload = service.checkpoints.read(current, expected_timeframe=Timeframe.HOUR_4)
    assert payload["as_of_date"] == second.isoformat()
    assert set(engine._states) == {"TPC", "TpC"}

    con = connect_utc(":memory:")
    try:
        output = service.paths.feature_file(Timeframe.HOUR_4, second)
        symbols = con.execute(
            f"SELECT DISTINCT symbol FROM read_parquet({sql_string(output)}) ORDER BY symbol"
        ).fetchall()
    finally:
        con.close()
    assert symbols == [("TPC",), ("TpC",)]

    # The current checkpoint makes an identical rerun idempotent without replaying
    # recursive history.
    rerun = service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=first,
        end=second,
        bootstrap_from_empty=True,
    )
    assert rerun.sessions_processed == 0
    assert rerun.rows_processed == 0
    assert rerun.checkpoint_as_of == second
