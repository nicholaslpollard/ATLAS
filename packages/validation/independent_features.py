from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd

from packages.features.feature_registry import CORE_FEATURE_REGISTRY


@dataclass
class _EMA:
    period: int
    count: int = 0
    seed_sum: float = 0.0
    value: float | None = None

    def push(self, x: float) -> float | None:
        if self.value is None:
            self.count += 1
            self.seed_sum += x
            if self.count < self.period:
                return None
            self.value = self.seed_sum / self.period
            return self.value
        alpha = 2.0 / (self.period + 1.0)
        self.value = self.value + alpha * (x - self.value)
        return self.value


@dataclass
class _Wilder:
    period: int
    count: int = 0
    seed_sum: float = 0.0
    value: float | None = None

    def push(self, x: float) -> float | None:
        if self.value is None:
            self.count += 1
            self.seed_sum += x
            if self.count < self.period:
                return None
            self.value = self.seed_sum / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + x) / self.period
        return self.value


def _mean(values: deque[float]) -> float:
    return float(sum(values) / len(values))


def _std(values: deque[float]) -> float:
    return float(np.asarray(values, dtype="float64").std(ddof=0))


def replay_core_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Independently replay the frozen 33-feature contract for one ordered stream.

    This module deliberately does not import the production incremental feature engine.
    It exists so cumulative acceptance can detect regressions in the persisted feature
    lake instead of validating production code with itself.
    """

    required = {"timestamp_utc", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("feature replay source missing columns: " + ", ".join(missing))
    if frame.empty:
        return pd.DataFrame(columns=("timestamp_utc", *(d.name for d in CORE_FEATURE_REGISTRY.all())))

    ordered = frame.sort_values("timestamp_utc", kind="stable").reset_index(drop=True)
    if ordered["timestamp_utc"].duplicated().any():
        raise ValueError("feature replay stream contains duplicate timestamps")

    ema20, ema50, ema200 = _EMA(20), _EMA(50), _EMA(200)
    ema12, ema26, macd_signal_state = _EMA(12), _EMA(26), _EMA(9)
    gain14, loss14, atr14_state = _Wilder(14), _Wilder(14), _Wilder(14)
    closes: deque[float] = deque(maxlen=20)
    highs: deque[float] = deque(maxlen=20)
    lows: deque[float] = deque(maxlen=20)
    volumes: deque[float] = deque(maxlen=20)
    dollar_volumes: deque[float] = deque(maxlen=20)
    log_returns: deque[float] = deque(maxlen=20)
    prior_close: float | None = None
    obv = 0.0
    obv_seeded = False
    rows: list[dict[str, object]] = []

    for source in ordered.itertuples(index=False):
        timestamp = pd.Timestamp(source.timestamp_utc)
        high = float(source.high)
        low = float(source.low)
        close = float(source.close)
        volume = float(source.volume)
        if not all(math.isfinite(x) for x in (high, low, close, volume)):
            raise ValueError("feature replay source contains nonfinite OHLCV")
        if high < low or close < low or close > high or volume < 0:
            raise ValueError("feature replay source contains invalid OHLCV")

        return_1 = None
        log_return_1 = None
        if prior_close is not None:
            if prior_close != 0.0:
                return_1 = close / prior_close - 1.0
            if close > 0.0 and prior_close > 0.0:
                log_return_1 = math.log(close / prior_close)

        true_range = high - low
        if prior_close is not None:
            true_range = max(true_range, abs(high - prior_close), abs(low - prior_close))
        atr_14 = atr14_state.push(true_range)
        natr_14 = atr_14 / close if atr_14 is not None and close > 0.0 else None

        rsi_14 = None
        if prior_close is not None:
            delta = close - prior_close
            avg_gain = gain14.push(max(delta, 0.0))
            avg_loss = loss14.push(max(-delta, 0.0))
            if avg_gain is not None and avg_loss is not None:
                if avg_gain == 0.0 and avg_loss == 0.0:
                    rsi_14 = 50.0
                elif avg_loss == 0.0:
                    rsi_14 = 100.0
                elif avg_gain == 0.0:
                    rsi_14 = 0.0
                else:
                    rs = avg_gain / avg_loss
                    rsi_14 = 100.0 - 100.0 / (1.0 + rs)

        old_ema20 = ema20.value
        ema_20 = ema20.push(close)
        ema_50 = ema50.push(close)
        ema_200 = ema200.push(close)
        ema_20_slope_1 = (
            ema_20 / old_ema20 - 1.0
            if ema_20 is not None and old_ema20 is not None and old_ema20 != 0.0
            else None
        )

        fast = ema12.push(close)
        slow = ema26.push(close)
        macd = None if fast is None or slow is None else fast - slow
        macd_signal = macd_signal_state.push(macd) if macd is not None else None
        macd_hist = None if macd is None or macd_signal is None else macd - macd_signal

        if not obv_seeded:
            obv = 0.0
            obv_seeded = True
        elif prior_close is not None:
            if close > prior_close:
                obv += volume
            elif close < prior_close:
                obv -= volume

        prior_high_20 = max(highs) if len(highs) == 20 else None
        prior_low_20 = min(lows) if len(lows) == 20 else None
        breakout = close / prior_high_20 - 1.0 if prior_high_20 and prior_high_20 > 0 else None
        breakdown = close / prior_low_20 - 1.0 if prior_low_20 and prior_low_20 > 0 else None

        directional_efficiency = None
        if len(closes) == 20:
            old_close = closes[0]
            path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
            path += abs(close - closes[-1])
            directional_efficiency = abs(close - old_close) / path if path else 0.0

        if log_return_1 is None:
            log_returns.clear()
        else:
            log_returns.append(log_return_1)
        dollar_volume = close * volume
        closes.append(close)
        highs.append(high)
        lows.append(low)
        volumes.append(volume)
        dollar_volumes.append(dollar_volume)

        sma_20 = _mean(closes) if len(closes) == 20 else None
        bb_mid = sma_20
        bb_upper = bb_lower = bb_width = bb_position = None
        if len(closes) == 20 and bb_mid is not None:
            s = _std(closes)
            bb_upper = bb_mid + 2.0 * s
            bb_lower = bb_mid - 2.0 * s
            bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid != 0.0 else None
            width = bb_upper - bb_lower
            bb_position = (close - bb_lower) / width if width != 0.0 else 0.5

        realized_volatility = _std(log_returns) if len(log_returns) == 20 else None
        avg_volume = _mean(volumes) if len(volumes) == 20 else None
        relative_volume = volume / avg_volume if avg_volume is not None and avg_volume > 0 else None
        volume_zscore = None
        if len(volumes) == 20 and avg_volume is not None:
            volume_std = _std(volumes)
            volume_zscore = (volume - avg_volume) / volume_std if volume_std != 0.0 else 0.0

        avg_dollar = _mean(dollar_volumes) if len(dollar_volumes) == 20 else None
        relative_dollar = dollar_volume / avg_dollar if avg_dollar is not None and avg_dollar > 0 else None
        rolling_high = max(highs) if len(highs) == 20 else None
        rolling_low = min(lows) if len(lows) == 20 else None
        range_position = None
        if rolling_high is not None and rolling_low is not None:
            width = rolling_high - rolling_low
            range_position = (close - rolling_low) / width if width else 0.5
        rolling_close_high = max(closes) if len(closes) == 20 else None
        drawdown = close / rolling_close_high - 1.0 if rolling_close_high and rolling_close_high > 0 else None
        price_distance = close / ema_20 - 1.0 if ema_20 is not None and ema_20 != 0.0 else None

        rows.append(
            {
                "timestamp_utc": timestamp,
                "return_1": return_1,
                "log_return_1": log_return_1,
                "sma_20": sma_20,
                "ema_20": ema_20,
                "ema_50": ema_50,
                "ema_200": ema_200,
                "rsi_14": rsi_14,
                "macd_12_26": macd,
                "macd_signal_12_26_9": macd_signal,
                "macd_hist_12_26_9": macd_hist,
                "true_range": true_range,
                "atr_14": atr_14,
                "natr_14": natr_14,
                "bb_mid_20": bb_mid,
                "bb_upper_20": bb_upper,
                "bb_lower_20": bb_lower,
                "bb_width_20": bb_width,
                "bb_position_20": bb_position,
                "realized_volatility_20": realized_volatility,
                "obv": obv,
                "relative_volume_20": relative_volume,
                "volume_zscore_20": volume_zscore,
                "dollar_volume": dollar_volume,
                "relative_dollar_volume_20": relative_dollar,
                "range_position_20": range_position,
                "prior_high_20": prior_high_20,
                "prior_low_20": prior_low_20,
                "breakout_distance_20": breakout,
                "breakdown_distance_20": breakdown,
                "drawdown_20": drawdown,
                "ema_20_slope_1": ema_20_slope_1,
                "price_distance_ema_20": price_distance,
                "directional_efficiency_20": directional_efficiency,
            }
        )
        prior_close = close

    result = pd.DataFrame(rows)
    expected = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
    missing_output = [name for name in expected if name not in result.columns]
    if missing_output:
        raise AssertionError("independent feature replay omitted: " + ", ".join(missing_output))
    return result[["timestamp_utc", *expected]]
