from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("duckdb")

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.continuity import FeatureContinuityVerifier
from packages.features.historical_materializer import HistoricalFeatureMaterializer
from packages.features.lake_audit import FeatureLakeAuditor


def make_settings(tmp_path: Path):
    settings = load_settings()
    settings.project_root = tmp_path
    return settings


def write_aapl_4h_source(
    materializer: HistoricalFeatureMaterializer,
    trading_date: date,
    close: float,
) -> None:
    path = materializer.partition_store.source_path(Timeframe.HOUR_4, trading_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "timestamp_utc": [
                datetime(
                    trading_date.year,
                    trading_date.month,
                    trading_date.day,
                    13,
                    30,
                    tzinfo=UTC,
                )
            ],
            "session_segment": ["regular"],
            "high": [close + 1.0],
            "low": [close - 1.0],
            "close": [close],
            "volume": [1_000.0 + close],
        }
    )
    con = connect_utc(":memory:")
    try:
        con.register("bars", frame)
        con.execute(f"COPY bars TO {sql_string(path)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()


def test_feature_lake_audit_validates_state_chain_and_tail_checkpoint(tmp_path):
    settings = make_settings(tmp_path)
    service = HistoricalFeatureMaterializer(settings)
    first = date(2026, 8, 13)
    second = date(2026, 8, 14)
    write_aapl_4h_source(service, first, 100.0)
    write_aapl_4h_source(service, second, 101.0)
    service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=first,
        end=second,
        bootstrap_from_empty=True,
    )

    result = FeatureLakeAuditor(settings).audit_timeframe(
        Timeframe.HOUR_4,
        start=first,
        end=second,
        deep_feature_sha=True,
    )
    assert result.passed
    assert result.manifest_sessions == 2
    assert result.total_rows == 2
    assert result.checkpoint_as_of == second
    assert result.checkpoint_matches_tail
    assert result.state_chain_breaks == ()

    manifest_path = service.paths.feature_manifest_file(Timeframe.HOUR_4, second)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["input_state_fingerprint"] = "tampered"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    broken = FeatureLakeAuditor(settings).audit_timeframe(
        Timeframe.HOUR_4,
        start=first,
        end=second,
    )
    assert not broken.passed
    assert broken.state_chain_breaks == (second,)


def test_checkpoint_hydration_continues_through_incremental_engine_without_discontinuity(tmp_path):
    settings = make_settings(tmp_path)
    service = HistoricalFeatureMaterializer(settings)
    sessions = [
        date(2026, 7, 30),
        date(2026, 7, 31),
        date(2026, 8, 3),
        date(2026, 8, 4),
    ]
    for index, trading_date in enumerate(sessions):
        write_aapl_4h_source(service, trading_date, 100.0 + index)

    service.materialize_range(
        timeframe=Timeframe.HOUR_4,
        start=sessions[0],
        end=sessions[-1],
        bootstrap_from_empty=True,
    )

    result = FeatureContinuityVerifier(settings).verify(
        timeframe=Timeframe.HOUR_4,
        target_date=sessions[-1],
        symbol="AAPL",
    )
    assert result.anchor_date == date(2026, 7, 31)
    assert result.replay_sessions == 2
    assert result.replay_source_rows == 2
    assert result.target_rows == 1
    assert result.features_compared == 33
    assert result.key_match
    assert result.failed_features == ()
    assert result.maximum_abs_diff == pytest.approx(0.0)
    assert result.passed
