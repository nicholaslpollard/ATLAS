from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from packages.features.gaps import gap_direction, gap_return
from packages.features.relative_strength import relative_return, relative_strength_change
from packages.features.session import regular_session_features


def test_gap_features_preserve_missing_and_direction():
    gap = gap_return(pd.Series([10.0, 9.0, 10.0, 5.0]), pd.Series([8.0, 10.0, 10.0, np.nan]))
    assert gap.iloc[0] == pytest.approx(0.25)
    assert gap.iloc[1] == pytest.approx(-0.10)
    assert gap.iloc[2] == pytest.approx(0.0)
    assert np.isnan(gap.iloc[3])
    direction = gap_direction(gap)
    assert direction.iloc[:3].tolist() == [1, -1, 0]
    assert pd.isna(direction.iloc[3])


def test_relative_return_uses_identical_bar_horizon():
    asset = pd.Series([100.0, 110.0, 121.0])
    benchmark = pd.Series([100.0, 105.0, 110.25])
    result = relative_return(asset, benchmark, 1)
    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.05)
    assert result.iloc[2] == pytest.approx(0.05)
    strength = relative_strength_change(asset, benchmark, 2)
    assert strength.iloc[:2].isna().all()
    assert strength.iloc[2] == pytest.approx((121.0 / 110.25) / (100.0 / 100.0) - 1.0)


def test_regular_session_features_reset_each_session_and_keep_symbol_state_separate():
    frame = pd.DataFrame(
        [
            # Non-regular row must not become the regular session open/close.
            {"symbol": "TPC", "timestamp_utc": "2026-08-14T12:00:00Z", "session_date": date(2026, 8, 14), "session_segment": "premarket", "open": 8.0, "high": 9.0, "low": 8.0, "close": 8.5},
            {"symbol": "TPC", "timestamp_utc": "2026-08-14T13:30:00Z", "session_date": date(2026, 8, 14), "session_segment": "regular", "open": 10.0, "high": 11.0, "low": 9.0, "close": 11.0},
            {"symbol": "TPC", "timestamp_utc": "2026-08-14T13:31:00Z", "session_date": date(2026, 8, 14), "session_segment": "regular", "open": 11.0, "high": 13.0, "low": 10.0, "close": 12.0},
            {"symbol": "TPC", "timestamp_utc": "2026-08-17T13:30:00Z", "session_date": date(2026, 8, 17), "session_segment": "regular", "open": 15.0, "high": 16.0, "low": 14.0, "close": 16.0},
            # Same letters but provider-native lowercase p: independent identity/state.
            {"symbol": "TpC", "timestamp_utc": "2026-08-17T13:30:00Z", "session_date": date(2026, 8, 17), "session_segment": "regular", "open": 50.0, "high": 51.0, "low": 49.0, "close": 50.5},
        ]
    )
    result = regular_session_features(frame)

    assert pd.isna(result.loc[0, "session_bar_index"])
    assert np.isnan(result.loc[0, "session_open"])

    assert result.loc[1, "session_bar_index"] == 0
    assert result.loc[2, "session_bar_index"] == 1
    assert result.loc[1, "session_open"] == 10.0
    assert result.loc[2, "session_high_to_date"] == 13.0
    assert result.loc[2, "session_low_to_date"] == 9.0

    # Second TPC session knows the prior regular close (12), not the premarket value.
    assert result.loc[3, "session_bar_index"] == 0
    assert result.loc[3, "previous_session_close"] == 12.0
    assert result.loc[3, "overnight_gap"] == pytest.approx(0.25)

    # TpC must not inherit TPC's previous close despite the similar ticker text.
    assert result.loc[4, "session_bar_index"] == 0
    assert np.isnan(result.loc[4, "previous_session_close"])
    assert np.isnan(result.loc[4, "overnight_gap"])
