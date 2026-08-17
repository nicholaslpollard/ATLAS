from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd
import pytest

from packages.core.enums import Timeframe
from packages.regimes.calibration import (
    BASKET_METRICS,
    BREADTH_METRICS,
    REGIME_CALIBRATION_CONTRACT_VERSION,
    REGIME_CALIBRATION_QUANTILES,
    RegimeCalibration,
    basket_daily,
    metric_quantiles,
    quantile_label,
    quantile_summary,
)


def test_regime_calibration_contract_and_quantiles_are_locked():
    assert REGIME_CALIBRATION_CONTRACT_VERSION == (
        "regime-calibration-v1-historical-activity-floor-proxy-distributions"
    )
    assert REGIME_CALIBRATION_QUANTILES == (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
    assert quantile_label(0.05) == "p05"
    assert quantile_label(0.90) == "p90"


def test_quantile_summary_is_deterministic_for_numeric_values():
    summary = quantile_summary(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert summary["min"] == 1.0
    assert summary["p50"] == 3.0
    assert summary["max"] == 5.0
    assert summary["p10"] == pytest.approx(1.4)
    assert summary["p90"] == pytest.approx(4.6)


def test_quantile_summary_returns_none_for_empty_numeric_evidence():
    summary = quantile_summary(pd.Series([None, "bad"]))
    assert summary["min"] is None
    assert summary["p05"] is None
    assert summary["p50"] is None
    assert summary["p95"] is None
    assert summary["max"] is None


def test_basket_daily_builds_fraction_and_median_evidence():
    frame = pd.DataFrame(
        {
            "trading_date": ["2026-08-14", "2026-08-14"],
            "symbol": ["SPY", "QQQ"],
            "close": [110.0, 90.0],
            "return_1": [0.01, -0.02],
            "ema_20": [100.0, 100.0],
            "ema_50": [95.0, 95.0],
            "ema_200": [90.0, 85.0],
            "rsi_14": [60.0, 40.0],
            "macd_hist_12_26_9": [1.0, -1.0],
            "natr_14": [0.01, 0.03],
            "realized_volatility_20": [0.20, 0.40],
            "directional_efficiency_20": [0.30, 0.50],
        }
    )
    daily = basket_daily(frame)
    assert tuple(column for column in daily.columns if column != "trading_date") == BASKET_METRICS
    assert len(daily) == 1
    row = daily.iloc[0]
    assert row["fraction_above_ema_20"] == pytest.approx(0.5)
    assert row["fraction_above_ema_200"] == pytest.approx(1.0)
    assert row["fraction_positive_return_1"] == pytest.approx(0.5)
    assert row["median_rsi_14"] == pytest.approx(50.0)
    assert row["median_natr_14"] == pytest.approx(0.02)


def test_metric_quantiles_covers_every_requested_metric():
    frame = pd.DataFrame({metric: [0.25, 0.50, 0.75] for metric in BREADTH_METRICS})
    summaries = metric_quantiles(frame, BREADTH_METRICS)
    assert tuple(summaries) == BREADTH_METRICS
    for metric in BREADTH_METRICS:
        assert summaries[metric]["p50"] == pytest.approx(0.50)


def test_calibration_joins_canonical_close_to_derived_features(tmp_path):
    feature_path = tmp_path / "features.parquet"
    bar_path = tmp_path / "bars.parquet"
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            f"""
            COPY (
                SELECT
                    'SPY'::VARCHAR AS symbol,
                    TIMESTAMPTZ '2026-08-14 20:00:00+00' AS timestamp_utc,
                    0.01::DOUBLE AS return_1,
                    100.0::DOUBLE AS ema_20,
                    95.0::DOUBLE AS ema_50,
                    90.0::DOUBLE AS ema_200,
                    60.0::DOUBLE AS rsi_14,
                    1.0::DOUBLE AS macd_hist_12_26_9,
                    0.01::DOUBLE AS natr_14,
                    0.20::DOUBLE AS realized_volatility_20,
                    0.30::DOUBLE AS directional_efficiency_20,
                    1000000.0::DOUBLE AS dollar_volume
            ) TO '{feature_path.as_posix()}' (FORMAT PARQUET)
            """
        )
        con.execute(
            f"""
            COPY (
                SELECT
                    'SPY'::VARCHAR AS symbol,
                    TIMESTAMPTZ '2026-08-14 20:00:00+00' AS timestamp_utc,
                    110.0::DOUBLE AS close
            ) TO '{bar_path.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    class FakePaths:
        def feature_glob(self, timeframe: Timeframe) -> str:
            assert timeframe == Timeframe.DAY_1
            return feature_path.as_posix()

        def glob_for_timeframe(self, timeframe: Timeframe) -> str:
            assert timeframe == Timeframe.DAY_1
            return bar_path.as_posix()

    calibration = object.__new__(RegimeCalibration)
    calibration.paths = FakePaths()

    breadth = calibration._breadth_daily(date(2026, 8, 14), date(2026, 8, 14))
    proxies = calibration._proxy_frame(date(2026, 8, 14), date(2026, 8, 14))

    assert len(breadth) == 1
    assert int(breadth.iloc[0]["participant_count"]) == 1
    assert breadth.iloc[0]["close_above_ema_20"] == pytest.approx(1.0)
    assert len(proxies) == 1
    assert proxies.iloc[0]["symbol"] == "SPY"
    assert proxies.iloc[0]["close"] == pytest.approx(110.0)
