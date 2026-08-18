from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from packages.features.engine import FeatureInputError, compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.momentum import macd, rsi_wilder
from packages.features.rolling import ema, wilder_average
from packages.features.structure import prior_rolling_high
from packages.features.volatility import atr_wilder, bollinger_bands, true_range
from packages.features.volume import on_balance_volume


def test_ema_uses_sma_seed_and_explicit_warmup():
    result = ema(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(3.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_wilder_average_uses_recursive_wilder_formula():
    result = wilder_average(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(8.0 / 3.0)
    assert result.iloc[4] == pytest.approx(31.0 / 9.0)


def test_rsi_matches_classic_wilder_reference_sequence():
    closes = pd.Series(
        [
            44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10,
            45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28,
            46.28, 46.00, 46.03, 46.41, 46.22, 45.64, 46.21,
        ]
    )
    expected = [
        70.4641350211,
        66.2496185536,
        66.4809418347,
        69.3468531629,
        66.2947126589,
        57.9150206701,
        62.8807183100,
    ]
    result = rsi_wilder(closes, 14)
    assert result.iloc[:14].isna().all()
    np.testing.assert_allclose(result.iloc[14:].to_numpy(), expected, rtol=0.0, atol=1e-9)


def test_rsi_flat_market_is_neutral_not_divide_by_zero():
    result = rsi_wilder(pd.Series([100.0] * 20), 14)
    assert result.iloc[:14].isna().all()
    assert (result.iloc[14:] == 50.0).all()


def test_true_range_and_atr_match_hand_calculated_wilder_values():
    high = pd.Series([10.0, 12.0, 13.0, 14.0])
    low = pd.Series([8.0, 9.0, 11.0, 10.0])
    close = pd.Series([9.0, 11.0, 12.0, 13.0])
    tr = true_range(high, low, close)
    np.testing.assert_allclose(tr.to_numpy(), [2.0, 3.0, 2.0, 4.0])

    atr = atr_wilder(high, low, close, 3)
    assert atr.iloc[:2].isna().all()
    assert atr.iloc[2] == pytest.approx(7.0 / 3.0)
    assert atr.iloc[3] == pytest.approx(26.0 / 9.0)


def test_macd_warmup_positions_are_explicit():
    result = macd(pd.Series(np.arange(1.0, 51.0)), fast=12, slow=26, signal=9)
    assert result["macd_12_26"].iloc[:25].isna().all()
    assert result["macd_12_26"].iloc[25] == pytest.approx(7.0)
    assert result["macd_signal_12_26_9"].iloc[:33].isna().all()
    assert result["macd_signal_12_26_9"].iloc[33] == pytest.approx(7.0)
    assert result["macd_hist_12_26_9"].iloc[33] == pytest.approx(0.0)


def test_bollinger_uses_population_standard_deviation():
    result = bollinger_bands(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), period=5)
    sqrt_two = np.sqrt(2.0)
    assert result["bb_mid_5"].iloc[4] == pytest.approx(3.0)
    assert result["bb_upper_5"].iloc[4] == pytest.approx(3.0 + 2.0 * sqrt_two)
    assert result["bb_lower_5"].iloc[4] == pytest.approx(3.0 - 2.0 * sqrt_two)


def test_obv_uses_zero_seed_and_price_direction():
    result = on_balance_volume(
        pd.Series([10.0, 11.0, 10.0, 10.0, 12.0]),
        pd.Series([100.0, 200.0, 300.0, 400.0, 500.0]),
    )
    np.testing.assert_allclose(result.to_numpy(), [0.0, 200.0, -100.0, -100.0, 400.0])


def test_prior_rolling_high_excludes_current_bar():
    result = prior_rolling_high(pd.Series([1.0, 2.0, 3.0, 100.0]), 3)
    assert result.iloc[:3].isna().all()
    assert result.iloc[3] == 3.0


def test_feature_registry_is_versioned_deterministic_and_marks_recursive_features():
    fingerprint = CORE_FEATURE_REGISTRY.fingerprint()
    assert len(fingerprint) == 64
    assert fingerprint == CORE_FEATURE_REGISTRY.fingerprint()
    assert CORE_FEATURE_REGISTRY.get("rsi_14").minimum_history_bars == 15
    assert CORE_FEATURE_REGISTRY.get("rsi_14").recursive is True
    assert CORE_FEATURE_REGISTRY.get("prior_high_20").minimum_history_bars == 21


def _engine_frame() -> pd.DataFrame:
    rows = []
    start = datetime(2026, 8, 14, 13, 30, tzinfo=UTC)
    for offset in range(25):
        for symbol, base in (("TPC", 100.0), ("TpC", 10.0)):
            close = base + offset
            rows.append(
                {
                    "symbol": symbol,
                    "timestamp_utc": start + timedelta(minutes=offset),
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1000.0 + offset,
                }
            )
    return pd.DataFrame(rows)


def test_core_engine_preserves_provider_case_and_never_crosses_symbols():
    result = compute_core_features(_engine_frame())
    assert result["symbol"].drop_duplicates().tolist() == ["TPC", "TpC"]
    for symbol in ("TPC", "TpC"):
        group = result[result["symbol"] == symbol].reset_index(drop=True)
        assert np.isnan(group.loc[0, "return_1"])
        assert group.loc[1, "return_1"] == pytest.approx(1.0 / (100.0 if symbol == "TPC" else 10.0))
        assert group.loc[:18, "sma_20"].isna().all()
        assert group.loc[19, "sma_20"] == pytest.approx(
            (109.5 if symbol == "TPC" else 19.5)
        )
    assert result.attrs["feature_contract_version"].startswith("features-v1-")
    assert len(result.attrs["feature_registry_fingerprint"]) == 64


def test_core_engine_rejects_duplicate_market_keys():
    frame = _engine_frame()
    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(FeatureInputError, match="duplicate"):
        compute_core_features(duplicate)
