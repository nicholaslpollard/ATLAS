from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


class IncrementalFeatureError(ValueError):
    pass


@dataclass(slots=True)
class _EMAState:
    period: int
    count: int = 0
    seed_sum: float = 0.0
    value: float | None = None

    def update(self, value: float) -> float | None:
        if self.value is None:
            self.count += 1
            self.seed_sum += value
            if self.count < self.period:
                return None
            self.value = self.seed_sum / self.period
            return self.value
        alpha = 2.0 / (self.period + 1.0)
        self.value = self.value + alpha * (value - self.value)
        return self.value


@dataclass(slots=True)
class _WilderState:
    period: int
    count: int = 0
    seed_sum: float = 0.0
    value: float | None = None

    def update(self, value: float) -> float | None:
        if self.value is None:
            self.count += 1
            self.seed_sum += value
            if self.count < self.period:
                return None
            self.value = self.seed_sum / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + value) / self.period
        return self.value


def _mean(values: deque[float]) -> float:
    return float(sum(values) / len(values))


def _population_std(values: deque[float]) -> float:
    array = np.asarray(values, dtype="float64")
    return float(array.std(ddof=0))


@dataclass(slots=True)
class IncrementalSymbolFeatureState:
    """Exact recursive + bounded rolling state for one provider-native symbol."""

    symbol: str
    last_timestamp_utc: datetime | None = None
    previous_close: float | None = None

    ema20: _EMAState = field(default_factory=lambda: _EMAState(20))
    ema50: _EMAState = field(default_factory=lambda: _EMAState(50))
    ema200: _EMAState = field(default_factory=lambda: _EMAState(200))
    ema12_macd: _EMAState = field(default_factory=lambda: _EMAState(12))
    ema26_macd: _EMAState = field(default_factory=lambda: _EMAState(26))
    macd_signal: _EMAState = field(default_factory=lambda: _EMAState(9))
    rsi_gain: _WilderState = field(default_factory=lambda: _WilderState(14))
    rsi_loss: _WilderState = field(default_factory=lambda: _WilderState(14))
    atr: _WilderState = field(default_factory=lambda: _WilderState(14))

    previous_ema20: float | None = None
    obv: float = 0.0
    has_obv_seed: bool = False

    closes: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    highs: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    lows: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    volumes: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    dollar_volumes: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    log_returns: deque[float] = field(default_factory=lambda: deque(maxlen=20))

    def update(
        self,
        *,
        timestamp_utc: datetime,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> dict[str, float | None]:
        if self.last_timestamp_utc is not None and timestamp_utc <= self.last_timestamp_utc:
            raise IncrementalFeatureError(
                f"non-increasing timestamp for {self.symbol}: {timestamp_utc.isoformat()}"
            )
        high = float(high)
        low = float(low)
        close = float(close)
        volume = float(volume)
        if not all(math.isfinite(value) for value in (high, low, close, volume)):
            raise IncrementalFeatureError("incremental OHLCV values must be finite")
        if high < low or close > high or close < low:
            raise IncrementalFeatureError("incremental bar has invalid OHLC geometry")
        if volume < 0.0:
            raise IncrementalFeatureError("incremental bar has negative volume")

        prior_close = self.previous_close
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
        atr14 = self.atr.update(true_range)
        natr14 = atr14 / close if atr14 is not None and close > 0.0 else None

        rsi14 = None
        if prior_close is not None:
            delta = close - prior_close
            avg_gain = self.rsi_gain.update(max(delta, 0.0))
            avg_loss = self.rsi_loss.update(max(-delta, 0.0))
            if avg_gain is not None and avg_loss is not None:
                if avg_gain == 0.0 and avg_loss == 0.0:
                    rsi14 = 50.0
                elif avg_loss == 0.0:
                    rsi14 = 100.0
                elif avg_gain == 0.0:
                    rsi14 = 0.0
                else:
                    rs = avg_gain / avg_loss
                    rsi14 = 100.0 - 100.0 / (1.0 + rs)

        previous_ema20 = self.ema20.value
        ema20 = self.ema20.update(close)
        ema50 = self.ema50.update(close)
        ema200 = self.ema200.update(close)
        ema20_slope = None
        if ema20 is not None and previous_ema20 is not None and previous_ema20 != 0.0:
            ema20_slope = ema20 / previous_ema20 - 1.0

        macd_fast = self.ema12_macd.update(close)
        macd_slow = self.ema26_macd.update(close)
        macd_line = None if macd_fast is None or macd_slow is None else macd_fast - macd_slow
        macd_signal = self.macd_signal.update(macd_line) if macd_line is not None else None
        macd_hist = None if macd_line is None or macd_signal is None else macd_line - macd_signal

        if not self.has_obv_seed:
            self.obv = 0.0
            self.has_obv_seed = True
        elif prior_close is not None:
            if close > prior_close:
                self.obv += volume
            elif close < prior_close:
                self.obv -= volume

        prior_high = max(self.highs) if len(self.highs) == 20 else None
        prior_low = min(self.lows) if len(self.lows) == 20 else None
        breakout = close / prior_high - 1.0 if prior_high is not None and prior_high > 0.0 else None
        breakdown = close / prior_low - 1.0 if prior_low is not None and prior_low > 0.0 else None

        directional_efficiency = None
        if len(self.closes) == 20:
            old_close = self.closes[0]
            previous_path = sum(
                abs(self.closes[index] - self.closes[index - 1])
                for index in range(1, len(self.closes))
            )
            current_step = abs(close - self.closes[-1])
            path = previous_path + current_step
            directional_efficiency = abs(close - old_close) / path if path != 0.0 else 0.0

        if log_return_1 is None:
            self.log_returns.clear()
        else:
            self.log_returns.append(log_return_1)

        dollar_volume = close * volume
        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)
        self.volumes.append(volume)
        self.dollar_volumes.append(dollar_volume)

        sma20 = _mean(self.closes) if len(self.closes) == 20 else None
        bb_mid = sma20
        bb_upper = bb_lower = bb_width = bb_position = None
        if len(self.closes) == 20 and bb_mid is not None:
            std = _population_std(self.closes)
            bb_upper = bb_mid + 2.0 * std
            bb_lower = bb_mid - 2.0 * std
            bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid != 0.0 else None
            width = bb_upper - bb_lower
            bb_position = (close - bb_lower) / width if width != 0.0 else 0.5

        realized_volatility = (
            _population_std(self.log_returns) if len(self.log_returns) == 20 else None
        )
        average_volume = _mean(self.volumes) if len(self.volumes) == 20 else None
        relative_volume = (
            volume / average_volume if average_volume is not None and average_volume > 0.0 else None
        )
        volume_zscore = None
        if len(self.volumes) == 20:
            volume_std = _population_std(self.volumes)
            volume_zscore = (volume - average_volume) / volume_std if volume_std != 0.0 else 0.0

        average_dollar = _mean(self.dollar_volumes) if len(self.dollar_volumes) == 20 else None
        relative_dollar = (
            dollar_volume / average_dollar
            if average_dollar is not None and average_dollar > 0.0
            else None
        )

        rolling_high = max(self.highs) if len(self.highs) == 20 else None
        rolling_low = min(self.lows) if len(self.lows) == 20 else None
        range_position = drawdown = None
        if rolling_high is not None and rolling_low is not None:
            width = rolling_high - rolling_low
            range_position = (close - rolling_low) / width if width != 0.0 else 0.5
            drawdown = close / rolling_high - 1.0 if rolling_high > 0.0 else None

        price_distance_ema20 = close / ema20 - 1.0 if ema20 is not None and ema20 != 0.0 else None

        self.previous_ema20 = ema20
        self.previous_close = close
        self.last_timestamp_utc = timestamp_utc

        return {
            "return_1": return_1,
            "log_return_1": log_return_1,
            "sma_20": sma20,
            "ema_20": ema20,
            "ema_50": ema50,
            "ema_200": ema200,
            "rsi_14": rsi14,
            "macd_12_26": macd_line,
            "macd_signal_12_26_9": macd_signal,
            "macd_hist_12_26_9": macd_hist,
            "true_range": true_range,
            "atr_14": atr14,
            "natr_14": natr14,
            "bb_mid_20": bb_mid,
            "bb_upper_20": bb_upper,
            "bb_lower_20": bb_lower,
            "bb_width_20": bb_width,
            "bb_position_20": bb_position,
            "realized_volatility_20": realized_volatility,
            "obv": self.obv,
            "relative_volume_20": relative_volume,
            "volume_zscore_20": volume_zscore,
            "dollar_volume": dollar_volume,
            "relative_dollar_volume_20": relative_dollar,
            "range_position_20": range_position,
            "prior_high_20": prior_high,
            "prior_low_20": prior_low,
            "breakout_distance_20": breakout,
            "breakdown_distance_20": breakdown,
            "drawdown_20": drawdown,
            "ema_20_slope_1": ema20_slope,
            "price_distance_ema_20": price_distance_ema20,
            "directional_efficiency_20": directional_efficiency,
        }


class IncrementalFeatureEngine:
    """Own exact feature state independently for each provider-native symbol."""

    def __init__(self) -> None:
        self._states: dict[str, IncrementalSymbolFeatureState] = {}

    def state_for(self, symbol: str) -> IncrementalSymbolFeatureState:
        symbol = symbol.strip()
        if not symbol:
            raise IncrementalFeatureError("symbol cannot be blank")
        state = self._states.get(symbol)
        if state is None:
            state = IncrementalSymbolFeatureState(symbol=symbol)
            self._states[symbol] = state
        return state

    def update(
        self,
        *,
        symbol: str,
        timestamp_utc: datetime,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> dict[str, float | None]:
        return self.state_for(symbol).update(
            timestamp_utc=timestamp_utc,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

    @property
    def symbol_count(self) -> int:
        return len(self._states)
