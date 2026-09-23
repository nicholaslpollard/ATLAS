from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.data.tradier_whole_universe_cadence import (
    normalize_quality,
    provider_epoch_to_utc,
    quality_summary,
    recovery_summary,
)


def _ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def test_provider_epoch_rejects_zero_and_parses_milliseconds() -> None:
    assert provider_epoch_to_utc(0) is None
    target = datetime(2026, 9, 23, 14, 0, tzinfo=UTC)
    assert provider_epoch_to_utc(_ms(target)) == target


def test_quality_treats_nonpositive_timestamps_as_unknown() -> None:
    captured = datetime(2026, 9, 23, 14, 0, 30, tzinfo=UTC)
    row = {
        "symbol": "SPY",
        "bid": 600.0,
        "ask": 600.1,
        "bid_date": 0,
        "ask_date": 0,
        "trade_date": 0,
        "average_volume": 10_000_000,
        "volume": 1_000_000,
    }
    quality = normalize_quality(row, symbol="SPY", captured_at=captured)
    assert quality.returned is True
    assert quality.geometry_valid is True
    assert quality.quote_age_seconds is None
    assert quality.trade_age_seconds is None
    assert quality.freshness_unresolved is True


def test_quality_uses_older_quote_side_for_age() -> None:
    captured = datetime(2026, 9, 23, 14, 0, 30, tzinfo=UTC)
    row = {
        "symbol": "SPY",
        "bid": 600.0,
        "ask": 600.1,
        "bid_date": _ms(captured - timedelta(seconds=7)),
        "ask_date": _ms(captured - timedelta(seconds=18)),
        "trade_date": _ms(captured - timedelta(seconds=4)),
        "average_volume": 10_000_000,
        "volume": 1_000_000,
    }
    quality = normalize_quality(row, symbol="SPY", captured_at=captured)
    assert quality.quote_age_seconds == 18.0
    assert quality.trade_age_seconds == 4.0
    assert quality.diagnostic_usable_30s_100bps is True


def test_quality_summary_preserves_missing_and_unresolved() -> None:
    captured = datetime(2026, 9, 23, 14, 0, 30, tzinfo=UTC)
    rows = (
        {
            "symbol": "SPY",
            "bid": 600.0,
            "ask": 600.1,
            "bid_date": _ms(captured - timedelta(seconds=5)),
            "ask_date": _ms(captured - timedelta(seconds=6)),
            "trade_date": _ms(captured - timedelta(seconds=3)),
            "average_volume": 10_000_000,
            "volume": 1_000_000,
        },
        {
            "symbol": "AAPL",
            "bid": 250.0,
            "ask": 250.2,
            "bid_date": _ms(captured - timedelta(seconds=45)),
            "ask_date": _ms(captured - timedelta(seconds=50)),
            "trade_date": _ms(captured - timedelta(seconds=20)),
            "average_volume": 5_000_000,
            "volume": 500_000,
        },
    )
    summary, quality = quality_summary(
        ("SPY", "AAPL", "MSFT"),
        rows,
        captured_at=captured,
    )
    assert summary["returned"] == 2
    assert summary["missing_symbols"] == ["MSFT"]
    assert summary["freshness_unresolved_count"] == 2
    assert quality["SPY"].freshness_unresolved is False
    assert quality["AAPL"].freshness_unresolved is True
    assert quality["MSFT"].returned is False


def test_recovery_summary_counts_missing_and_freshness_recovery() -> None:
    captured = datetime(2026, 9, 23, 14, 0, 30, tzinfo=UTC)
    before_rows = (
        {
            "symbol": "AAPL",
            "bid": 250.0,
            "ask": 250.2,
            "bid_date": _ms(captured - timedelta(seconds=50)),
            "ask_date": _ms(captured - timedelta(seconds=55)),
            "trade_date": _ms(captured - timedelta(seconds=30)),
        },
    )
    _, before = quality_summary(
        ("AAPL", "MSFT"),
        before_rows,
        captured_at=captured,
    )

    later = captured + timedelta(seconds=10)
    after_rows = (
        {
            "symbol": "AAPL",
            "bid": 250.1,
            "ask": 250.2,
            "bid_date": _ms(later - timedelta(seconds=2)),
            "ask_date": _ms(later - timedelta(seconds=3)),
            "trade_date": _ms(later - timedelta(seconds=2)),
        },
        {
            "symbol": "MSFT",
            "bid": 520.0,
            "ask": 520.1,
            "bid_date": _ms(later - timedelta(seconds=2)),
            "ask_date": _ms(later - timedelta(seconds=2)),
            "trade_date": _ms(later - timedelta(seconds=1)),
        },
    )
    _, after = quality_summary(
        ("AAPL", "MSFT"),
        after_rows,
        captured_at=later,
    )

    recovery = recovery_summary(before, after, ("AAPL", "MSFT"))
    assert recovery["missing_recovered"] == 1
    assert recovery["freshness_recovered"] == 2
    assert recovery["newer_quote_timestamp"] == 2
    assert recovery["still_unresolved"] == 0
