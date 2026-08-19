from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.data.duckdb_connection import connect_utc
from packages.regimes.ticker_probe import TickerRegimeProbe


class _FeaturePaths:
    def __init__(self, feature_path: Path) -> None:
        self.feature_path = feature_path

    def feature_glob(self, _timeframe: object) -> str:
        return self.feature_path.as_posix()


def test_ticker_history_counts_create_view_uses_non_parameterized_as_of_date(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.parquet"
    con = connect_utc(":memory:")
    try:
        con.execute(
            f"""
            COPY (
                SELECT * FROM (VALUES
                    ('AAA', TIMESTAMPTZ '2026-08-14 20:00:00+00', 10.0, 9.0, 8.0, 55.0, 0.1, 0.02, 0.03, 0.25),
                    ('AAA', TIMESTAMPTZ '2026-08-17 20:00:00+00', 10.1, 9.1, 8.1, 56.0, 0.2, 0.02, 0.03, 0.26)
                ) AS t(symbol, timestamp_utc, ema_20, ema_50, ema_200, rsi_14,
                       macd_hist_12_26_9, natr_14, realized_volatility_20,
                       directional_efficiency_20)
            ) TO '{feature_path.as_posix()}' (FORMAT PARQUET)
            """
        )
        con.execute(
            """
            CREATE TEMP VIEW atlas_ticker_population AS
            SELECT 'AAA'::VARCHAR AS ticker, 1::BIGINT AS current_ticker_identity_count
            """
        )

        probe = TickerRegimeProbe.__new__(TickerRegimeProbe)
        probe.paths = _FeaturePaths(feature_path)
        probe._history_counts(con, date(2026, 8, 14))

        row = con.execute(
            "SELECT symbol, complete_history_sessions FROM atlas_daily_history_counts"
        ).fetchone()
        assert row == ("AAA", 1)
    finally:
        con.close()
