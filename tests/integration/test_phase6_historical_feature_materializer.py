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
from packages.features.incremental import feature_stream_key


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
            "session_segment": ["regular", "regular"],
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


def write_segmented_aapl_source(
    materializer: HistoricalFeatureMaterializer,
    d: date,
    *,
    premarket_close: float,
    regular_close: float,
) -> None:
    path = materializer.partition_store.source_path(Timeframe.HOUR_4, d)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL"],
            "timestamp_utc": [
                datetime(d.year, d.month, d.day, 8, 0, tzinfo=UTC),
                datetime(d.year, d.month, d.day, 13, 30, tzinfo=UTC),
            ],
            "session_segment": ["premarket", "regular"],
            "high": [premarket_close + 1.0, regular_close + 1.0],
            "low": [premarket_close - 1.0, regular_close - 1.0],
            "close": [premarket_close, regular_close],
            "volume": [500.0, 1000.0],
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
    assert set(engine._states) == {
        feature_stream_key("TPC", "regular"),
        feature_stream_key("TpC", "regular"),
    }
    assert {state.symbol for state in engine._states.values()} == {"TPC", "TpC"}

    con = connect_utc(":memory:")
    try:
        output = service.paths.feature_file(Timeframe.HOUR_4, second)
        symbols = con.execute(
            f"SELECT DISTINCT symbol FROM read_parquet({sql_string(output)}) ORDER BY symbol"
        ).fetchall()
        segments = con.execute(
            f"SELECT DISTINCT session_segment FROM read_parquet({sql_string(output)})"
        ).fetchall()
    finally:
        con.close()
    assert symbols == [("TPC",), ("TpC",)]
    assert segments == [("regular",)]

    rerun = service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=first,
        end=second,
        bootstrap_from_empty=True,
    )
    assert rerun.sessions_processed == 0
    assert rerun.rows_processed == 0
    assert rerun.checkpoint_as_of == second


def test_intraday_recursive_features_do_not_cross_session_segments(tmp_path):
    service = HistoricalFeatureMaterializer(make_settings(tmp_path))
    first = date(2026, 8, 13)
    second = date(2026, 8, 14)
    write_segmented_aapl_source(
        service,
        first,
        premarket_close=10.0,
        regular_close=100.0,
    )
    write_segmented_aapl_source(
        service,
        second,
        premarket_close=20.0,
        regular_close=110.0,
    )

    service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=first,
        end=second,
        bootstrap_from_empty=True,
    )

    current = service.paths.feature_current_state_file(Timeframe.HOUR_4)
    engine, payload = service.checkpoints.read(current, expected_timeframe=Timeframe.HOUR_4)
    assert payload["state_count"] == 2
    assert payload["symbol_count"] == 1
    assert set(engine._states) == {
        feature_stream_key("AAPL", "premarket"),
        feature_stream_key("AAPL", "regular"),
    }

    con = connect_utc(":memory:")
    try:
        output = service.paths.feature_file(Timeframe.HOUR_4, second)
        rows = con.execute(
            f"""
            SELECT session_segment, return_1
            FROM read_parquet({sql_string(output)})
            WHERE symbol='AAPL'
            ORDER BY session_segment
            """
        ).fetchall()
    finally:
        con.close()
    values = dict(rows)
    assert values["premarket"] == pytest.approx(1.0)
    assert values["regular"] == pytest.approx(0.10)


def test_corrected_source_replays_from_latest_monthly_anchor(tmp_path):
    service = HistoricalFeatureMaterializer(make_settings(tmp_path))
    sessions = [
        date(2026, 7, 30),
        date(2026, 7, 31),
        date(2026, 8, 3),
        date(2026, 8, 4),
    ]
    for index, session in enumerate(sessions):
        write_4h_source(service, session, float(index))

    initial = service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=sessions[0],
        end=sessions[-1],
        bootstrap_from_empty=True,
    )
    assert initial.sessions_processed == 4
    anchor = service.latest_anchor_before(Timeframe.HOUR_4, date(2026, 8, 3))
    assert anchor is not None
    assert anchor[0] == date(2026, 7, 31)

    downstream_before = service.partition_store.read_manifest(
        Timeframe.HOUR_4, date(2026, 8, 4)
    )
    assert downstream_before is not None

    write_4h_source(service, date(2026, 8, 3), 20.0)
    assert service.stale_source_sessions(
        timeframe=Timeframe.HOUR_4,
        start=date(2026, 8, 3),
        end=date(2026, 8, 4),
    ) == (date(2026, 8, 3),)

    replay = service.replay_from_correction(
        timeframe=Timeframe.HOUR_4,
        corrected_date=date(2026, 8, 3),
        end=date(2026, 8, 4),
        history_start=date(2026, 7, 30),
    )
    assert replay.effective_start == date(2026, 8, 3)
    assert replay.effective_end == date(2026, 8, 4)
    assert replay.sessions_processed == 2

    downstream_after = service.partition_store.read_manifest(
        Timeframe.HOUR_4, date(2026, 8, 4)
    )
    assert downstream_after is not None
    assert downstream_after.input_state_fingerprint != downstream_before.input_state_fingerprint
    assert service.stale_source_sessions(
        timeframe=Timeframe.HOUR_4,
        start=date(2026, 8, 3),
        end=date(2026, 8, 4),
    ) == ()
