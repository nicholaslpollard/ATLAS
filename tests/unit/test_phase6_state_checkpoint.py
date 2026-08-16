from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.enums import Timeframe
from packages.features.incremental import IncrementalFeatureEngine
from packages.features.state_checkpoint import FeatureStateCheckpointStore


def _feed(engine: IncrementalFeatureEngine, *, symbol: str, count: int, start: datetime) -> None:
    rng = np.random.default_rng(44 if symbol == "TPC" else 45)
    price = 100.0 if symbol == "TPC" else 20.0
    for index in range(count):
        price *= float(np.exp(rng.normal(0.0003, 0.01)))
        engine.update(
            symbol=symbol,
            timestamp_utc=start + timedelta(hours=index),
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=float(1000 + index),
        )


def test_feature_state_checkpoint_roundtrip_continues_exactly(tmp_path):
    start = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)
    original = IncrementalFeatureEngine()
    _feed(original, symbol="TPC", count=45, start=start)
    _feed(original, symbol="TpC", count=45, start=start)

    store = FeatureStateCheckpointStore()
    path = tmp_path / "state.json.gz"
    fingerprint = store.write(
        path,
        original,
        timeframe=Timeframe.HOUR_1,
        as_of_date="2026-01-05",
    )
    restored, payload = store.read(path, expected_timeframe=Timeframe.HOUR_1)

    assert len(fingerprint) == 64
    assert payload["checkpoint_fingerprint"] == fingerprint
    assert restored.symbol_count == 2

    timestamp = start + timedelta(hours=45)
    next_bar = dict(timestamp_utc=timestamp, high=155.0, low=150.0, close=152.0, volume=9000.0)
    expected = original.update(symbol="TPC", **next_bar)
    actual = restored.update(symbol="TPC", **next_bar)
    assert expected.keys() == actual.keys()
    for name in expected:
        if expected[name] is None:
            assert actual[name] is None
        else:
            assert actual[name] == pytest.approx(expected[name], rel=1e-14, abs=1e-14)


def test_feature_state_checkpoint_rejects_wrong_timeframe(tmp_path):
    engine = IncrementalFeatureEngine()
    start = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)
    _feed(engine, symbol="TPC", count=1, start=start)
    path = tmp_path / "state.json.gz"
    store = FeatureStateCheckpointStore()
    store.write(path, engine, timeframe=Timeframe.HOUR_4, as_of_date="2026-01-02")
    with pytest.raises(ValueError, match="timeframe mismatch"):
        store.read(path, expected_timeframe=Timeframe.HOUR_1)
