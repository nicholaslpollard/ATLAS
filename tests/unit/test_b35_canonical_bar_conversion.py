from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from packages.backtesting.b35_development_replay import _canonical_bars
from packages.schemas.market import CanonicalBar

_FIELDS = (
    "symbol", "timestamp_utc", "session_date", "timeframe", "session_segment",
    "open", "high", "low", "close", "volume", "vwap", "transaction_count",
    "provider", "dataset", "source_id", "is_adjusted", "provider_timestamp_utc",
)


def _legacy_reference(frame: pd.DataFrame) -> tuple[CanonicalBar, ...]:
    bars: list[CanonicalBar] = []
    for record in frame.to_dict(orient="records"):
        payload: dict[str, object] = {}
        for field in _FIELDS:
            value = record.get(field)
            if field in {"vwap", "transaction_count"} and pd.isna(value):
                value = None
            payload[field] = value
        bars.append(CanonicalBar.model_validate(payload))
    return tuple(bars)


def test_canonical_bars_itertuples_matches_legacy_validated_conversion() -> None:
    premarket_stamp = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    regular_stamp = datetime(2026, 4, 30, 13, 30, tzinfo=UTC)
    frame = pd.DataFrame([
        {
            "symbol": "TpC", "timestamp_utc": premarket_stamp,
            "session_date": date(2026, 4, 30), "timeframe": "1m",
            "session_segment": "premarket", "open": 10.0, "high": 10.2,
            "low": 9.9, "close": 10.1, "volume": 100.0, "vwap": None,
            "transaction_count": None, "provider": "alpaca",
            "dataset": "stock_minute_aggregates", "source_id": "test-source-1",
            "is_adjusted": False, "provider_timestamp_utc": premarket_stamp,
        },
        {
            "symbol": "TEST", "timestamp_utc": regular_stamp,
            "session_date": date(2026, 4, 30), "timeframe": "1m",
            "session_segment": "regular", "open": 20.0, "high": 20.5,
            "low": 19.8, "close": 20.3, "volume": 250.0, "vwap": 20.2,
            "transaction_count": 7, "provider": "alpaca",
            "dataset": "stock_minute_aggregates", "source_id": "test-source-2",
            "is_adjusted": False, "provider_timestamp_utc": regular_stamp,
        },
    ])

    expected = _legacy_reference(frame)
    actual = _canonical_bars(frame)
    assert [item.model_dump(mode="python") for item in actual] == [
        item.model_dump(mode="python") for item in expected
    ]
    assert [type(item.session_segment) for item in actual] == [
        type(item.session_segment) for item in expected
    ]
    assert [type(item.timeframe) for item in actual] == [
        type(item.timeframe) for item in expected
    ]
    assert [item.symbol for item in actual] == ["TpC", "TEST"]
