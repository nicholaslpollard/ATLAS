from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import Timeframe
from packages.features.incremental import IncrementalFeatureEngine, IncrementalFeatureError
from packages.features.state_checkpoint import FeatureStateCheckpointStore


def _bar(timestamp: datetime, close: float, volume: float = 1000.0) -> dict[str, object]:
    return {
        "timestamp_utc": timestamp,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": volume,
    }


def test_drop_state_resets_next_observation_to_genesis() -> None:
    start = datetime(2021, 8, 13, 13, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="RESET", **_bar(start, 100.0))
    engine.update(symbol="RESET", **_bar(start + timedelta(days=1), 110.0))

    assert engine.drop_state("RESET") is True
    assert engine.has_state("RESET") is False
    assert engine.drop_state("RESET") is False

    fresh = engine.update(symbol="RESET", **_bar(start + timedelta(days=3), 150.0))
    assert fresh["return_1"] is None
    assert fresh["log_return_1"] is None
    assert fresh["obv"] == 0.0


def test_transfer_state_preserves_recursive_history_under_successor_literal() -> None:
    start = datetime(2020, 1, 2, 14, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="OLD", **_bar(start, 100.0))
    engine.update(symbol="OLD", **_bar(start + timedelta(days=1), 110.0))

    engine.transfer_state("OLD", "NEW")

    assert engine.has_state("OLD") is False
    assert engine.has_state("NEW") is True
    assert engine.state_count == 1
    result = engine.update(symbol="NEW", **_bar(start + timedelta(days=2), 121.0))
    assert result["return_1"] == pytest.approx(0.1)
    assert result["obv"] == pytest.approx(2000.0)


def test_transfer_state_missing_source_fails_closed() -> None:
    engine = IncrementalFeatureEngine()
    with pytest.raises(IncrementalFeatureError, match="source is missing"):
        engine.transfer_state("OLD", "NEW")


def test_transfer_state_occupied_target_fails_without_mutating_either_stream() -> None:
    start = datetime(2020, 1, 2, 14, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="OLD", **_bar(start, 100.0))
    engine.update(symbol="NEW", **_bar(start, 50.0))

    with pytest.raises(IncrementalFeatureError, match="target already exists"):
        engine.transfer_state("OLD", "NEW")

    assert engine.has_state("OLD") is True
    assert engine.has_state("NEW") is True
    assert engine.state_count == 2


def test_transfer_state_never_casefolds_exact_provider_literals() -> None:
    start = datetime(2020, 1, 2, 14, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="TPC", **_bar(start, 100.0))

    engine.transfer_state("TPC", "TpC")

    assert engine.has_state("TPC") is False
    assert engine.has_state("TpC") is True
    continued = engine.update(symbol="TpC", **_bar(start + timedelta(days=1), 105.0))
    assert continued["return_1"] == pytest.approx(0.05)


def test_transfer_state_rejects_same_exact_key() -> None:
    start = datetime(2020, 1, 2, 14, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="SAME", **_bar(start, 100.0))
    with pytest.raises(IncrementalFeatureError, match="keys are identical"):
        engine.transfer_state("SAME", "SAME")
    assert engine.has_state("SAME") is True


def test_checkpoint_roundtrip_preserves_transferred_identity_and_state(tmp_path) -> None:
    start = datetime(2020, 1, 2, 14, 30, tzinfo=UTC)
    original = IncrementalFeatureEngine()
    for index in range(25):
        original.update(
            symbol="OLD",
            **_bar(start + timedelta(days=index), 100.0 + index, 1000.0 + index),
        )
    original.transfer_state("OLD", "NEW")

    store = FeatureStateCheckpointStore()
    path = tmp_path / "transferred.json.gz"
    store.write(path, original, timeframe=Timeframe.DAY_1, as_of_date="2020-01-26")
    restored, _payload = store.read(path, expected_timeframe=Timeframe.DAY_1)

    assert restored.has_state("OLD") is False
    assert restored.has_state("NEW") is True
    next_bar = _bar(start + timedelta(days=25), 130.0, 2000.0)
    expected = original.update(symbol="NEW", **next_bar)
    actual = restored.update(symbol="NEW", **next_bar)
    for name, value in expected.items():
        if value is None:
            assert actual[name] is None
        else:
            assert actual[name] == pytest.approx(value, rel=1e-14, abs=1e-14)
