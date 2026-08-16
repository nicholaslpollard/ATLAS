from __future__ import annotations

import pandas as pd

from packages.features.feature_registry import (
    CORE_FEATURE_CONTRACT_VERSION,
    CORE_FEATURE_REGISTRY,
)
from packages.features.momentum import log_return, macd, rsi_wilder, simple_return
from packages.features.rolling import ema, sma
from packages.features.structure import (
    breakdown_distance,
    breakout_distance,
    drawdown_from_rolling_high,
    prior_rolling_high,
    prior_rolling_low,
    rolling_range_position,
)
from packages.features.trend import (
    directional_efficiency,
    moving_average_slope,
    price_distance_from_average,
)
from packages.features.volatility import (
    atr_wilder,
    bollinger_bands,
    normalized_atr,
    realized_volatility,
    true_range,
)
from packages.features.volume import (
    dollar_volume,
    on_balance_volume,
    relative_dollar_volume,
    relative_volume,
    volume_zscore,
)


CORE_BAR_COLUMNS = ("symbol", "timestamp_utc", "high", "low", "close", "volume")


class FeatureInputError(ValueError):
    pass


def _validate_input(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in CORE_BAR_COLUMNS if column not in frame.columns]
    if missing:
        raise FeatureInputError(f"feature input is missing required columns: {', '.join(missing)}")
    result = frame.copy()
    result["symbol"] = result["symbol"].astype("string").str.strip()
    if result["symbol"].isna().any() or (result["symbol"] == "").any():
        raise FeatureInputError("feature input contains a blank symbol")
    if "session_segment" in result.columns:
        result["session_segment"] = result["session_segment"].astype("string").str.strip()
        if result["session_segment"].isna().any() or (result["session_segment"] == "").any():
            raise FeatureInputError("feature input contains a blank session_segment")
    result["timestamp_utc"] = pd.to_datetime(result["timestamp_utc"], utc=True, errors="raise")
    for column in ("high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("float64")
    if result[["high", "low", "close", "volume"]].isna().any().any():
        raise FeatureInputError("feature input contains missing/non-numeric OHLCV values")
    if (result["volume"] < 0.0).any():
        raise FeatureInputError("feature input contains negative volume")
    if (result["high"] < result["low"]).any():
        raise FeatureInputError("feature input contains high < low")
    outside = (result["close"] > result["high"]) | (result["close"] < result["low"])
    if outside.any():
        raise FeatureInputError("feature input contains close outside [low, high]")
    duplicate_key = ["symbol", "timestamp_utc"]
    if "session_segment" in result.columns:
        duplicate_key.append("session_segment")
    if result.duplicated(duplicate_key).any():
        raise FeatureInputError("feature input contains duplicate market keys")
    sort_columns = ["symbol"]
    if "session_segment" in result.columns:
        sort_columns.append("session_segment")
    sort_columns.append("timestamp_utc")
    return result.sort_values(sort_columns, kind="stable").reset_index(drop=True)


def _compute_symbol_features(group: pd.DataFrame) -> pd.DataFrame:
    close = group["close"]
    high = group["high"]
    low = group["low"]
    volume = group["volume"]

    features = pd.DataFrame(index=group.index)
    features["return_1"] = simple_return(close, 1)
    features["log_return_1"] = log_return(close, 1)
    features["sma_20"] = sma(close, 20)
    features["ema_20"] = ema(close, 20)
    features["ema_50"] = ema(close, 50)
    features["ema_200"] = ema(close, 200)
    features["rsi_14"] = rsi_wilder(close, 14)

    macd_frame = macd(close, fast=12, slow=26, signal=9)
    features["macd_12_26"] = macd_frame["macd_12_26"]
    features["macd_signal_12_26_9"] = macd_frame["macd_signal_12_26_9"]
    features["macd_hist_12_26_9"] = macd_frame["macd_hist_12_26_9"]

    features["true_range"] = true_range(high, low, close)
    features["atr_14"] = atr_wilder(high, low, close, 14)
    features["natr_14"] = normalized_atr(high, low, close, 14)
    bands = bollinger_bands(close, period=20, standard_deviations=2.0)
    for column in bands.columns:
        features[column] = bands[column]
    features["realized_volatility_20"] = realized_volatility(close, period=20)

    features["obv"] = on_balance_volume(close, volume)
    features["relative_volume_20"] = relative_volume(volume, 20)
    features["volume_zscore_20"] = volume_zscore(volume, 20)
    features["dollar_volume"] = dollar_volume(close, volume)
    features["relative_dollar_volume_20"] = relative_dollar_volume(close, volume, 20)

    features["range_position_20"] = rolling_range_position(close, high, low, 20)
    features["prior_high_20"] = prior_rolling_high(high, 20)
    features["prior_low_20"] = prior_rolling_low(low, 20)
    features["breakout_distance_20"] = breakout_distance(close, high, 20)
    features["breakdown_distance_20"] = breakdown_distance(close, low, 20)
    features["drawdown_20"] = drawdown_from_rolling_high(close, 20)

    features["ema_20_slope_1"] = moving_average_slope(close, period=20, lag=1, kind="ema")
    features["price_distance_ema_20"] = price_distance_from_average(close, period=20, kind="ema")
    features["directional_efficiency_20"] = directional_efficiency(close, 20)
    return features


def compute_core_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute the Phase 6 core feature contract without cross-stream leakage.

    Provider-native symbol case is preserved. If ``session_segment`` is present,
    premarket, regular, and after-hours bars form independent recursive/rolling
    streams for the same symbol. Source columns are retained and feature columns are
    appended with calculation-contract metadata in DataFrame attrs.
    """

    ordered = _validate_input(frame)
    grouping: str | list[str] = "symbol"
    if "session_segment" in ordered.columns:
        grouping = ["symbol", "session_segment"]
    feature_parts: list[pd.DataFrame] = []
    for _, group in ordered.groupby(grouping, sort=False, observed=True):
        feature_parts.append(_compute_symbol_features(group))
    features = pd.concat(feature_parts).sort_index() if feature_parts else pd.DataFrame(index=ordered.index)
    result = pd.concat([ordered, features], axis=1)
    result.attrs["feature_contract_version"] = CORE_FEATURE_CONTRACT_VERSION
    result.attrs["feature_registry_fingerprint"] = CORE_FEATURE_REGISTRY.fingerprint()
    return result
