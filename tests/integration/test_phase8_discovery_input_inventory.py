from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.discovery.input_inventory import DiscoveryInputInventory

ROOT = Path(__file__).resolve().parents[2]


def _settings(tmp_path: Path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    return settings


def _write_rows(path: Path, ddl: str, rows: list[tuple[object, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"CREATE TABLE t ({ddl})")
        placeholders = ", ".join("?" for _ in rows[0])
        con.executemany(f"INSERT INTO t VALUES ({placeholders})", rows)
        con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()


def test_inventory_measures_exact_universe_bar_feature_coverage_and_activity(tmp_path: Path):
    settings = _settings(tmp_path)
    paths = MarketDataPaths(settings)
    as_of = date(2026, 8, 14)
    ts = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)

    _write_rows(
        paths.universe_snapshot_file(as_of),
        "instrument_id VARCHAR, ticker VARCHAR, security_type VARCHAR, discovery_eligible BOOLEAN",
        [
            ("i-aapl", "AAPL", "CS", True),
            ("i-etf", "ETF1", "ETF", True),
            ("i-miss", "MISS", "CS", True),
        ],
    )
    _write_rows(
        paths.canonical_file(Timeframe.DAY_1, as_of),
        "symbol VARCHAR, timestamp_utc TIMESTAMPTZ, close DOUBLE, volume DOUBLE",
        [
            ("AAPL", ts, 100.0, 1_000_000.0),
            ("ETF1", ts, 20.0, 0.0),
            ("OUTSIDE", ts, 5.0, 10_000.0),
        ],
    )
    _write_rows(
        paths.feature_file(Timeframe.DAY_1, as_of),
        "symbol VARCHAR, timestamp_utc TIMESTAMPTZ, dollar_volume DOUBLE, "
        "relative_volume_20 DOUBLE, relative_dollar_volume_20 DOUBLE, "
        "natr_14 DOUBLE, realized_volatility_20 DOUBLE",
        [
            ("AAPL", ts, 100_000_000.0, 1.2, 1.3, 0.02, 0.01),
            ("ETF1", ts, 0.0, 0.8, 0.7, 0.03, 0.015),
            ("OUTSIDE", ts, 50_000.0, 1.0, 1.0, 0.04, 0.02),
        ],
    )
    _write_rows(
        paths.feature_file(Timeframe.HOUR_4, as_of),
        "symbol VARCHAR, session_segment VARCHAR",
        [
            ("AAPL", "regular"),
            ("AAPL", "after_hours"),
            ("ETF1", "regular"),
            ("OUTSIDE", "regular"),
        ],
    )
    _write_rows(
        paths.feature_file(Timeframe.HOUR_1, as_of),
        "symbol VARCHAR, session_segment VARCHAR",
        [
            ("AAPL", "regular"),
            ("ETF1", "premarket"),
            ("OUTSIDE", "after_hours"),
        ],
    )

    report = DiscoveryInputInventory(settings).run(as_of)

    assert report.universe_count == 3
    assert report.duplicate_universe_tickers == 0

    daily = report.coverage["1d"]
    assert daily.total_feature_rows == 3
    assert daily.distinct_feature_symbols == 3
    assert daily.matched_universe_symbols == 2
    assert daily.missing_universe_symbols == 1

    four_hour = report.coverage["4h"]
    assert four_hour.total_feature_rows == 4
    assert four_hour.distinct_feature_symbols == 3
    assert four_hour.matched_universe_symbols == 2
    assert four_hour.missing_universe_symbols == 1
    assert four_hour.regular_session_symbols == 3
    assert four_hour.after_hours_symbols == 1

    one_hour = report.coverage["1h"]
    assert one_hour.matched_universe_symbols == 2
    assert one_hour.regular_session_symbols == 1
    assert one_hour.premarket_symbols == 1
    assert one_hour.after_hours_symbols == 1

    assert report.daily_quality["matched_universe"] == 2
    assert report.daily_quality["missing_universe"] == 1
    assert report.daily_quality["matched_daily_bars"] == 2
    assert report.daily_quality["missing_daily_bars"] == 1
    assert report.daily_quality["matched_daily_features"] == 2
    assert report.daily_quality["missing_daily_features"] == 1
    assert report.daily_quality["bar_feature_key_mismatch"] == 0
    assert report.daily_quality["invalid_or_nonpositive_close"] == 0
    assert report.daily_quality["zero_volume"] == 1
    assert report.daily_quality["nonpositive_or_missing_dollar_volume"] == 1

    assert report.quantiles["close"].finite_count == 2
    assert report.quantiles["close"].missing_or_nonfinite_count == 1
    assert report.threshold_counts["dollar_volume"][">=1m"] == 1
    assert report.combined_activity_counts["close>=1|dollar_volume>=1m"] == 1

    report_path = paths.discovery_input_inventory_report(as_of)
    assert report_path.exists()
    assert report.report_path == str(report_path)
    assert set(report.source_sha256) == {
        "universe",
        "bars_1d",
        "features_1d",
        "features_4h",
        "features_1h",
    }
