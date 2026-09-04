from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pandas as pd

from packages.features.engine import CORE_FEATURE_OUTPUT_COLUMNS, compute_core_features
from packages.features.rolling import sma
from packages.features.trend import moving_average_slope
from packages.schemas.strategy_policy import StrategySpecification


REFERENCE_DAILY_FEATURE_CONTRACT_VERSION = (
    "reference-daily-features-v1-identity-stream-prior-liquidity-state-transitions"
)
REFERENCE_DAILY_SIGNAL_CONTRACT_VERSION = (
    "reference-daily-signal-v1-trigger-plus-finite-warmup-no-universe-or-route"
)
REFERENCE_DAILY_REQUIRED_COLUMNS = (
    "instrument_id",
    "ticker",
    "session_date",
    "timestamp_utc",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "unadjusted_close",
    "pit_active",
    "security_type",
    "identity_clear",
    "price_adjustment_mode",
    "raw_price_lineage_id",
)
REFERENCE_DAILY_DERIVED_COLUMNS = (
    "history_sessions",
    "sma_50",
    "sma_200",
    "ema_50_slope_1",
    "prior_median_dollar_volume_20",
    "bb_width_p10_prior_126",
    "sma_cross_50_200_up",
    "sma_cross_50_200_down",
    "macd_signal_cross_up",
    "macd_signal_cross_down",
    "macd_signal_cross_up_below_zero",
    "macd_signal_cross_down_above_zero",
    "rsi_recovery_14_above_30_ema_200_long",
    "donchian_breakout_20_volume_long",
    "donchian_breakout_20_volume_short",
    "bb_squeeze_20_126",
    "bollinger_squeeze_breakout_20_long",
    "bollinger_squeeze_breakout_20_short",
    "ema_pullback_recovery_20_50_long",
    "ema_pullback_low_20_50_long",
    "ema_pullback_sessions_20_50_long",
    "universe_pit_active_ok",
    "universe_common_stock_ok",
    "universe_identity_ok",
    "universe_close_ok",
    "universe_prior_liquidity_ok",
    "reference_common_universe_eligible",
)


class ReferenceDailyFeatureInputError(ValueError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def reference_daily_feature_fingerprint() -> str:
    return _stable_hash(
        {
            "contract_version": REFERENCE_DAILY_FEATURE_CONTRACT_VERSION,
            "required_columns": REFERENCE_DAILY_REQUIRED_COLUMNS,
            "derived_columns": REFERENCE_DAILY_DERIVED_COLUMNS,
            "feature_stream_key": "instrument_id",
            "prior_liquidity": "median(close*volume) over prior 20 sessions excluding current",
            "price_floor": "same-session unadjusted close; never a future split-adjusted level",
            "squeeze_threshold": "current width versus prior 126 valid widths; signal requires prior-session squeeze",
            "ema_pullback": "one-to-five sessions; transition from above into EMA20 plus-or-minus 0.5 ATR, never closes below EMA50, first close recovery",
        }
    )


def _validate_input(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [name for name in REFERENCE_DAILY_REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise ReferenceDailyFeatureInputError(
            f"reference daily input is missing required columns: {', '.join(missing)}"
        )
    result = frame.copy()
    for column in ("instrument_id", "ticker", "security_type", "price_adjustment_mode", "raw_price_lineage_id"):
        result[column] = result[column].astype("string").str.strip()
        if result[column].isna().any() or (result[column] == "").any():
            raise ReferenceDailyFeatureInputError(f"reference daily input contains blank {column}")
    if (result["price_adjustment_mode"] != "SPLIT_ADJUSTED").any():
        raise ReferenceDailyFeatureInputError(
            "reference daily analytical bars must declare SPLIT_ADJUSTED price lineage"
        )

    result["timestamp_utc"] = pd.to_datetime(result["timestamp_utc"], utc=True, errors="raise")
    result["session_date"] = pd.to_datetime(result["session_date"], errors="raise").dt.date
    if (result["timestamp_utc"].dt.date != result["session_date"]).any():
        raise ReferenceDailyFeatureInputError("timestamp_utc date must match session_date")

    for column in ("open", "high", "low", "close", "volume", "unadjusted_close"):
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("float64")
    values = result[
        ["open", "high", "low", "close", "volume", "unadjusted_close"]
    ].to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise ReferenceDailyFeatureInputError("reference daily OHLCV must be finite")
    if (result[["open", "high", "low", "close"]] <= 0.0).any().any():
        raise ReferenceDailyFeatureInputError("reference daily prices must be positive")
    if (result["volume"] < 0.0).any():
        raise ReferenceDailyFeatureInputError("reference daily volume cannot be negative")
    if (result["unadjusted_close"] <= 0.0).any():
        raise ReferenceDailyFeatureInputError(
            "reference daily unadjusted_close must be positive"
        )
    if (
        (result["high"] < result[["open", "close"]].max(axis=1))
        | (result["low"] > result[["open", "close"]].min(axis=1))
        | (result["high"] < result["low"])
    ).any():
        raise ReferenceDailyFeatureInputError("reference daily OHLC geometry is invalid")

    for column in ("pit_active", "identity_clear"):
        if result[column].isna().any():
            raise ReferenceDailyFeatureInputError(f"reference daily input contains unknown {column}")
        if not result[column].map(lambda value: isinstance(value, (bool, np.bool_))).all():
            raise ReferenceDailyFeatureInputError(f"{column} must contain explicit booleans")
        result[column] = result[column].astype(bool)

    if result.duplicated(["instrument_id", "session_date"]).any():
        raise ReferenceDailyFeatureInputError("duplicate instrument/session rows are forbidden")
    if result.duplicated(["instrument_id", "timestamp_utc"]).any():
        raise ReferenceDailyFeatureInputError("duplicate instrument/timestamp rows are forbidden")
    return result.sort_values(
        ["instrument_id", "session_date", "timestamp_utc"], kind="stable"
    ).reset_index(drop=True)


def _binary(mask: pd.Series, valid: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=mask.index, dtype="float64")
    result.loc[valid] = mask.loc[valid].astype("float64")
    return result


def ema_pullback_state(group: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    trigger = pd.Series(0.0, index=group.index, dtype="float64")
    pullback_low = pd.Series(np.nan, index=group.index, dtype="float64")
    pullback_sessions = pd.Series(np.nan, index=group.index, dtype="float64")

    active = False
    active_low = math.nan
    active_sessions = 0
    for position in range(1, len(group)):
        idx = group.index[position]
        previous = group.iloc[position - 1]
        current = group.iloc[position]
        required = (
            previous["close"],
            previous["low"],
            previous["ema_20"],
            previous["atr_14"],
            current["close"],
            current["high"],
            current["low"],
            current["ema_20"],
            current["ema_50"],
            current["atr_14"],
        )
        if not all(math.isfinite(float(value)) for value in required):
            active = False
            active_low = math.nan
            active_sessions = 0
            trigger.loc[idx] = np.nan
            continue

        trend_valid = float(current["ema_20"]) > float(current["ema_50"])
        close_above_slow = float(current["close"]) >= float(current["ema_50"])
        if active:
            active_sessions += 1
            active_low = min(active_low, float(current["low"]))
            recovered = float(current["close"]) > float(current["ema_20"])
            if not trend_valid or not close_above_slow:
                active = False
            elif recovered and active_sessions <= 5:
                trigger.loc[idx] = 1.0
                pullback_low.loc[idx] = active_low
                pullback_sessions.loc[idx] = float(active_sessions)
                active = False
            elif active_sessions >= 5 or float(current["close"]) > float(current["ema_20"]):
                active = False
            if not active:
                active_low = math.nan
                active_sessions = 0
            continue

        tolerance = 0.5 * float(current["atr_14"])
        intersects_fast_ema_zone = (
            float(current["low"]) <= float(current["ema_20"]) + tolerance
            and float(current["high"]) >= float(current["ema_20"]) - tolerance
        )
        starts_pullback = (
            trend_valid
            and close_above_slow
            and float(previous["close"]) > float(previous["ema_20"])
            and float(previous["low"])
            > float(previous["ema_20"]) + 0.5 * float(previous["atr_14"])
            and intersects_fast_ema_zone
        )
        if starts_pullback:
            if float(current["close"]) > float(current["ema_20"]):
                trigger.loc[idx] = 1.0
                pullback_low.loc[idx] = float(current["low"])
                pullback_sessions.loc[idx] = 1.0
            else:
                active = True
                active_low = float(current["low"])
                active_sessions = 1

    return trigger, pullback_low, pullback_sessions


def _compute_overlay(group: pd.DataFrame) -> pd.DataFrame:
    close = group["close"]
    result = pd.DataFrame(index=group.index)
    result["history_sessions"] = np.arange(1, len(group) + 1, dtype="float64")
    result["sma_50"] = sma(close, 50)
    result["sma_200"] = sma(close, 200)
    result["ema_50_slope_1"] = moving_average_slope(close, period=50, lag=1, kind="ema")
    result["prior_median_dollar_volume_20"] = (
        (close * group["volume"]).shift(1).rolling(20, min_periods=20).median()
    )
    result["bb_width_p10_prior_126"] = (
        group["bb_width_20"].shift(1).rolling(126, min_periods=126).quantile(0.10)
    )

    fast = result["sma_50"]
    slow = result["sma_200"]
    ma_valid = fast.notna() & slow.notna() & fast.shift(1).notna() & slow.shift(1).notna()
    result["sma_cross_50_200_up"] = _binary(
        (fast.shift(1) <= slow.shift(1)) & (fast > slow), ma_valid
    )
    result["sma_cross_50_200_down"] = _binary(
        (fast.shift(1) >= slow.shift(1)) & (fast < slow), ma_valid
    )

    macd_line = group["macd_12_26"]
    macd_signal = group["macd_signal_12_26_9"]
    macd_valid = (
        macd_line.notna()
        & macd_signal.notna()
        & macd_line.shift(1).notna()
        & macd_signal.shift(1).notna()
    )
    cross_up = (macd_line.shift(1) <= macd_signal.shift(1)) & (macd_line > macd_signal)
    cross_down = (macd_line.shift(1) >= macd_signal.shift(1)) & (macd_line < macd_signal)
    result["macd_signal_cross_up"] = _binary(cross_up, macd_valid)
    result["macd_signal_cross_down"] = _binary(cross_down, macd_valid)
    result["macd_signal_cross_up_below_zero"] = _binary(
        cross_up & (macd_line < 0.0) & (macd_signal < 0.0), macd_valid
    )
    result["macd_signal_cross_down_above_zero"] = _binary(
        cross_down & (macd_line > 0.0) & (macd_signal > 0.0), macd_valid
    )

    rsi = group["rsi_14"]
    rsi_valid = rsi.notna() & rsi.shift(1).notna() & group["ema_200"].notna()
    result["rsi_recovery_14_above_30_ema_200_long"] = _binary(
        (rsi.shift(1) < 30.0) & (rsi > 30.0) & (close > group["ema_200"]), rsi_valid
    )

    breakout = group["breakout_distance_20"]
    breakdown = group["breakdown_distance_20"]
    donchian_valid = (
        breakout.notna()
        & breakout.shift(1).notna()
        & breakdown.notna()
        & breakdown.shift(1).notna()
        & result["ema_50_slope_1"].notna()
        & group["relative_volume_20"].notna()
    )
    result["donchian_breakout_20_volume_long"] = _binary(
        (breakout.shift(1) <= 0.0)
        & (breakout > 0.0)
        & (group["relative_volume_20"] >= 1.5)
        & (result["ema_50_slope_1"] > 0.0),
        donchian_valid,
    )
    result["donchian_breakout_20_volume_short"] = _binary(
        (breakdown.shift(1) >= 0.0)
        & (breakdown < 0.0)
        & (group["relative_volume_20"] >= 1.5)
        & (result["ema_50_slope_1"] < 0.0),
        donchian_valid,
    )

    squeeze_valid = group["bb_width_20"].notna() & result["bb_width_p10_prior_126"].notna()
    squeeze = group["bb_width_20"] <= result["bb_width_p10_prior_126"]
    result["bb_squeeze_20_126"] = _binary(squeeze, squeeze_valid)
    band_valid = (
        result["bb_squeeze_20_126"].shift(1).notna()
        & group["bb_upper_20"].notna()
        & group["bb_lower_20"].notna()
        & group["bb_upper_20"].shift(1).notna()
        & group["bb_lower_20"].shift(1).notna()
        & group["relative_volume_20"].notna()
    )
    prior_squeeze = result["bb_squeeze_20_126"].shift(1) == 1.0
    result["bollinger_squeeze_breakout_20_long"] = _binary(
        prior_squeeze
        & (close.shift(1) <= group["bb_upper_20"].shift(1))
        & (close > group["bb_upper_20"])
        & (group["relative_volume_20"] >= 1.25),
        band_valid,
    )
    result["bollinger_squeeze_breakout_20_short"] = _binary(
        prior_squeeze
        & (close.shift(1) >= group["bb_lower_20"].shift(1))
        & (close < group["bb_lower_20"])
        & (group["relative_volume_20"] >= 1.25),
        band_valid,
    )

    pullback_trigger, pullback_low, pullback_sessions = ema_pullback_state(group)
    result["ema_pullback_recovery_20_50_long"] = pullback_trigger
    result["ema_pullback_low_20_50_long"] = pullback_low
    result["ema_pullback_sessions_20_50_long"] = pullback_sessions

    result["universe_pit_active_ok"] = group["pit_active"].astype("float64")
    result["universe_common_stock_ok"] = (group["security_type"].str.upper() == "CS").astype("float64")
    result["universe_identity_ok"] = group["identity_clear"].astype("float64")
    result["universe_close_ok"] = (group["unadjusted_close"] >= 5.0).astype("float64")
    result["universe_prior_liquidity_ok"] = (
        result["prior_median_dollar_volume_20"] >= 5_000_000.0
    ).astype("float64")
    result["reference_common_universe_eligible"] = (
        (result["universe_pit_active_ok"] == 1.0)
        & (result["universe_common_stock_ok"] == 1.0)
        & (result["universe_identity_ok"] == 1.0)
        & (result["universe_close_ok"] == 1.0)
        & (result["universe_prior_liquidity_ok"] == 1.0)
    ).astype("float64")
    return result


def compute_reference_daily_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the A33/B33 daily overlay without changing the accepted 33-feature core."""

    ordered = _validate_input(frame)
    core_input = ordered.copy()
    core_input["symbol"] = core_input["instrument_id"]
    core = compute_core_features(core_input)
    core[list(CORE_FEATURE_OUTPUT_COLUMNS)] = core[list(CORE_FEATURE_OUTPUT_COLUMNS)].apply(
        pd.to_numeric, errors="coerce"
    ).astype("float64")
    parts = [
        _compute_overlay(group)
        for _, group in core.groupby("instrument_id", sort=False, observed=True)
    ]
    overlay = pd.concat(parts).sort_index() if parts else pd.DataFrame(index=core.index)
    result = pd.concat([core, overlay], axis=1)
    result = result.drop(columns=["symbol"])
    result.attrs["reference_daily_feature_contract_version"] = (
        REFERENCE_DAILY_FEATURE_CONTRACT_VERSION
    )
    result.attrs["reference_daily_feature_fingerprint"] = reference_daily_feature_fingerprint()
    result.attrs["core_feature_contract_version"] = core.attrs.get("feature_contract_version")
    result.attrs["core_feature_registry_fingerprint"] = core.attrs.get(
        "feature_registry_fingerprint"
    )
    return result


def reference_signal_mask(
    features: pd.DataFrame,
    specification: StrategySpecification,
) -> pd.Series:
    missing = [name for name in specification.signal.required_features if name not in features.columns]
    if "history_sessions" not in features.columns:
        missing.append("history_sessions")
    if missing:
        raise KeyError(f"reference signal frame missing required features: {', '.join(sorted(set(missing)))}")
    required = features[list(specification.signal.required_features)].apply(
        pd.to_numeric, errors="coerce"
    )
    finite = np.isfinite(required.to_numpy(dtype="float64")).all(axis=1)
    warm = features["history_sessions"] >= specification.signal.minimum_history_sessions
    trigger = features[specification.signal.trigger_feature] == 1.0
    return pd.Series(finite, index=features.index) & warm & trigger


REFERENCE_DAILY_FEATURE_FINGERPRINT = (
    "ee7e09b680b64b65280dea88c01d402bd9576a04cc70bc7748d8e3048ff57159"
)
if reference_daily_feature_fingerprint() != REFERENCE_DAILY_FEATURE_FINGERPRINT:
    raise RuntimeError("frozen reference daily feature fingerprint drifted")
