from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from packages.features.reference_daily import (
    REFERENCE_DAILY_FEATURE_FINGERPRINT,
    ReferenceDailyFeatureInputError,
    compute_reference_daily_features,
    ema_pullback_state,
    reference_daily_feature_fingerprint,
    reference_signal_mask,
)
from packages.strategies.reference_library import REFERENCE_STRATEGY_CATALOG


def _daily_frame(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    instrument_id: str = "figi:TEST",
    ticker: str = "TEST",
) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02", periods=len(closes), freq="B", tz="UTC")
    volumes = volumes or [100_000.0] * len(closes)
    return pd.DataFrame(
        {
            "instrument_id": instrument_id,
            "ticker": ticker,
            "session_date": timestamps.date,
            "timestamp_utc": timestamps,
            "open": closes,
            "high": [value + 1.0 for value in closes],
            "low": [value - 1.0 for value in closes],
            "close": closes,
            "volume": volumes,
            "unadjusted_close": closes,
            "pit_active": True,
            "security_type": "CS",
            "identity_clear": True,
            "price_adjustment_mode": "SPLIT_ADJUSTED",
            "raw_price_lineage_id": "raw-bars-v1",
        }
    )


def test_reference_feature_contract_is_separate_and_frozen() -> None:
    assert reference_daily_feature_fingerprint() == REFERENCE_DAILY_FEATURE_FINGERPRINT
    result = compute_reference_daily_features(_daily_frame([100.0] * 25))
    assert result.attrs["reference_daily_feature_fingerprint"] == REFERENCE_DAILY_FEATURE_FINGERPRINT
    assert result.attrs["core_feature_contract_version"].startswith("features-v1-")


def test_golden_cross_is_a_transition_not_merely_fast_above_slow() -> None:
    result = compute_reference_daily_features(_daily_frame([100.0] * 200 + [200.0]))
    assert result.loc[199, "sma_50"] == pytest.approx(100.0)
    assert result.loc[199, "sma_200"] == pytest.approx(100.0)
    assert result.loc[200, "sma_cross_50_200_up"] == 1.0
    specification = REFERENCE_STRATEGY_CATALOG.get("ma_trend_cross_50_200_long_v1")
    assert reference_signal_mask(result, specification).tolist().count(True) == 1


def test_prior_liquidity_excludes_current_signal_session() -> None:
    volumes = [1_000.0] * 20 + [10_000_000.0]
    result = compute_reference_daily_features(_daily_frame([100.0] * 21, volumes=volumes))
    assert result.loc[20, "prior_median_dollar_volume_20"] == pytest.approx(100_000.0)
    assert result.loc[20, "universe_prior_liquidity_ok"] == 0.0
    assert result.loc[20, "reference_common_universe_eligible"] == 0.0


def test_price_floor_uses_pit_unadjusted_close_not_future_split_scale() -> None:
    frame = _daily_frame([4.0] * 21, volumes=[2_000_000.0] * 21)
    frame["unadjusted_close"] = 40.0

    result = compute_reference_daily_features(frame)

    assert result.loc[20, "close"] == 4.0
    assert result.loc[20, "unadjusted_close"] == 40.0
    assert result.loc[20, "universe_close_ok"] == 1.0


def test_bollinger_breakout_requires_a_prior_session_squeeze() -> None:
    closes = [100.0] * 146 + [120.0]
    volumes = [100_000.0] * 146 + [2_000_000.0]
    result = compute_reference_daily_features(_daily_frame(closes, volumes=volumes))
    assert result.loc[145, "bb_squeeze_20_126"] == 1.0
    assert result.loc[146, "bollinger_squeeze_breakout_20_long"] == 1.0
    specification = REFERENCE_STRATEGY_CATALOG.get("bollinger_squeeze_breakout_20_long_v1")
    assert reference_signal_mask(result, specification).iloc[146]


def test_ema_pullback_state_is_bounded_and_emits_first_recovery_only() -> None:
    group = pd.DataFrame(
        {
            "close": [110.0, 104.0, 104.5, 106.0, 107.0],
            "high": [111.0, 105.5, 105.0, 107.0, 108.0],
            "low": [109.0, 103.5, 103.0, 104.0, 106.0],
            "ema_20": [105.0] * 5,
            "ema_50": [100.0] * 5,
            "atr_14": [2.0] * 5,
        }
    )
    trigger, pullback_low, sessions = ema_pullback_state(group)
    assert trigger.tolist() == [0.0, 0.0, 0.0, 1.0, 0.0]
    assert pullback_low.iloc[3] == 103.0
    assert sessions.iloc[3] == 3.0
    assert np.isnan(pullback_low.iloc[4])


def test_ema_pullback_one_bar_touch_and_recovery_is_explicit() -> None:
    group = pd.DataFrame(
        {
            "close": [110.0, 106.0, 108.0],
            "high": [111.0, 108.0, 109.0],
            "low": [109.0, 104.5, 107.0],
            "ema_20": [105.0] * 3,
            "ema_50": [100.0] * 3,
            "atr_14": [2.0] * 3,
        }
    )
    trigger, pullback_low, sessions = ema_pullback_state(group)
    assert trigger.tolist() == [0.0, 1.0, 0.0]
    assert pullback_low.iloc[1] == 104.5
    assert sessions.iloc[1] == 1.0


def test_reference_input_fails_closed_without_adjustment_lineage() -> None:
    frame = _daily_frame([100.0] * 25)
    frame.loc[0, "price_adjustment_mode"] = "RAW"
    with pytest.raises(ReferenceDailyFeatureInputError, match="SPLIT_ADJUSTED"):
        compute_reference_daily_features(frame)
