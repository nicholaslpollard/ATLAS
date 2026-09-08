from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from packages.data.b34_intraday_readiness import validate_sample_ohlcv


def _write_sample(path: Path, *, bad_geometry: bool = False) -> None:
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE bars(
                symbol VARCHAR,
                timestamp_utc TIMESTAMPTZ,
                session_date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                vwap DOUBLE,
                transaction_count BIGINT
            )
            """
        )
        high = 99.0 if bad_geometry else 101.0
        con.execute(
            "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "TEST",
                datetime(2026, 4, 30, 13, 30, tzinfo=UTC),
                date(2026, 4, 30),
                100.0,
                high,
                99.0,
                100.5,
                1000.0,
                100.25,
                10,
            ],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        con.execute("COPY bars TO ? (FORMAT PARQUET)", [str(path)])
    finally:
        con.close()


def test_ohlcv_readiness_accepts_valid_sample(tmp_path: Path) -> None:
    path = tmp_path / "valid.parquet"
    _write_sample(path)
    report = validate_sample_ohlcv(
        {
            "sample_class": "liquid_symbol_day",
            "symbol": "TEST",
            "session_date": "2026-04-30",
            "canonical_path": str(path),
            "row_count": 1,
            "allow_empty": False,
        }
    )
    assert report["accepted"] is True
    assert report["row_count"] == 1
    assert report["errors"] == []


def test_ohlcv_readiness_rejects_invalid_geometry(tmp_path: Path) -> None:
    path = tmp_path / "invalid.parquet"
    _write_sample(path, bad_geometry=True)
    report = validate_sample_ohlcv(
        {
            "sample_class": "liquid_symbol_day",
            "symbol": "TEST",
            "session_date": "2026-04-30",
            "canonical_path": str(path),
            "row_count": 1,
            "allow_empty": False,
        }
    )
    assert report["accepted"] is False
    assert any("OHLC geometry" in error for error in report["errors"])


def test_ohlcv_readiness_preserves_zero_row_absence() -> None:
    report = validate_sample_ohlcv(
        {
            "sample_class": "sparse_or_no_trade_symbol_day",
            "symbol": "TEST",
            "session_date": "2026-04-30",
            "canonical_path": "does-not-need-to-exist.parquet",
            "row_count": 0,
            "allow_empty": True,
        }
    )
    assert report["accepted"] is True
    assert report["row_count"] == 0
    assert "no synthetic OHLCV row" in report["note"]
