from __future__ import annotations

import pandas as pd
import pytest

from packages.regimes.calibration import (
    BASKET_METRICS,
    BREADTH_METRICS,
    REGIME_CALIBRATION_CONTRACT_VERSION,
    REGIME_CALIBRATION_QUANTILES,
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
