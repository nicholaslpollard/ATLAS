from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from packages.features.engine import compute_core_features
from packages.features.incremental import IncrementalFeatureEngine, feature_stream_key


def test_batch_engine_isolates_intraday_session_segments():
    start = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)
    frame = pd.DataFrame(
        [
            {"symbol": "AAPL", "timestamp_utc": start, "session_segment": "premarket", "high": 11.0, "low": 9.0, "close": 10.0, "volume": 100.0},
            {"symbol": "AAPL", "timestamp_utc": start + timedelta(hours=5, minutes=30), "session_segment": "regular", "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000.0},
            {"symbol": "AAPL", "timestamp_utc": start + timedelta(days=1), "session_segment": "premarket", "high": 21.0, "low": 19.0, "close": 20.0, "volume": 200.0},
            {"symbol": "AAPL", "timestamp_utc": start + timedelta(days=1, hours=5, minutes=30), "session_segment": "regular", "high": 111.0, "low": 109.0, "close": 110.0, "volume": 1100.0},
        ]
    )

    output = compute_core_features(frame)
    second = output.groupby("session_segment", observed=True).tail(1).set_index("session_segment")
    assert second.loc["premarket", "return_1"] == pytest.approx(1.0)
    assert second.loc["regular", "return_1"] == pytest.approx(0.10)


def test_incremental_engine_can_hold_multiple_session_streams_for_one_symbol():
    engine = IncrementalFeatureEngine()
    base = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)
    pre_key = feature_stream_key("AAPL", "premarket")
    reg_key = feature_stream_key("AAPL", "regular")

    engine.update(symbol="AAPL", state_key=pre_key, timestamp_utc=base, high=11, low=9, close=10, volume=100)
    engine.update(symbol="AAPL", state_key=reg_key, timestamp_utc=base + timedelta(hours=5), high=101, low=99, close=100, volume=1000)
    pre = engine.update(symbol="AAPL", state_key=pre_key, timestamp_utc=base + timedelta(days=1), high=21, low=19, close=20, volume=200)
    reg = engine.update(symbol="AAPL", state_key=reg_key, timestamp_utc=base + timedelta(days=1, hours=5), high=111, low=109, close=110, volume=1100)

    assert pre["return_1"] == pytest.approx(1.0)
    assert reg["return_1"] == pytest.approx(0.10)
    assert engine.state_count == 2
    assert engine.symbol_count == 1
