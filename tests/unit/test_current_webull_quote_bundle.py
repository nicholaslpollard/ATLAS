from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.core.enums import SessionSegment
from packages.core.settings import load_settings
from packages.execution.current_webull_quote_bundle import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
    CurrentWebullStockQuoteBundleError,
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
    parse_current_webull_stock_quote_v1,
    read_current_webull_stock_quote_bundle_v1,
    write_current_webull_stock_quote_bundle_v1,
)


REGULAR = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)


def _settings(tmp_path: Path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _quote(symbol: str, *, second: int = 0) -> CurrentWebullStockQuoteV1:
    stamp = REGULAR + timedelta(seconds=second)
    return CurrentWebullStockQuoteV1(
        symbol=symbol,
        provider_timestamp_utc=stamp,
        received_at_utc=stamp + timedelta(seconds=1),
        session_date=stamp.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0 + second,
        bid_size=10,
        ask_price=100.1 + second,
        ask_size=12,
    )


def _payload(symbol: str, *, quote_time: datetime = REGULAR):
    return [
        {
            "symbol": symbol,
            "bids": [{"price": "100.00", "size": "10"}],
            "asks": [{"price": "100.10", "size": "12"}],
            "quote_time": int(quote_time.timestamp() * 1000),
        }
    ]


def test_current_webull_quote_bundle_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
        == "5c2df876e2d9814434d6823f04c2cd0e6bfcdbe9b071cf291213abb634f2d26d"
    )


def test_bundle_is_sorted_complete_and_self_fingerprinted(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("MSFT", "AAPL"),
        quotes=(_quote("MSFT", second=1), _quote("AAPL")),
        captured_at_utc=REGULAR + timedelta(seconds=3),
    )
    assert bundle.requested_symbols == ("AAPL", "MSFT")
    assert tuple(x.symbol for x in bundle.quotes) == ("AAPL", "MSFT")
    assert bundle.provider_read_calls == 2
    assert len(bundle.bundle_fingerprint) == 64
    assert bundle.provider_writes == 0
    assert bundle.broker_reads == 0
    assert bundle.broker_writes == 0
    assert bundle.paper_authority is False
    assert bundle.live_authority is False

    path = write_current_webull_stock_quote_bundle_v1(
        settings,
        bundle,
    )
    restored = read_current_webull_stock_quote_bundle_v1(
        settings,
        path=path,
        now_utc=REGULAR + timedelta(seconds=5),
    )
    assert restored == bundle


def test_bundle_refuses_partial_requested_symbol_coverage() -> None:
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="failed validation",
    ):
        build_current_webull_stock_quote_bundle_v1(
            requested_symbols=("AAPL", "MSFT"),
            quotes=(_quote("AAPL"),),
            captured_at_utc=REGULAR + timedelta(seconds=2),
        )


def test_bundle_refuses_duplicate_requested_symbol() -> None:
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="cannot duplicate",
    ):
        build_current_webull_stock_quote_bundle_v1(
            requested_symbols=("AAPL", "AAPL"),
            quotes=(_quote("AAPL"),),
            captured_at_utc=REGULAR + timedelta(seconds=2),
        )


def test_parse_webull_quote_requires_exact_requested_symbol(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="exact requested symbol",
    ):
        parse_current_webull_stock_quote_v1(
            settings=settings,
            payload=_payload("aapl"),
            symbol="AAPL",
            received_at_utc=REGULAR + timedelta(seconds=1),
        )


def test_parse_webull_quote_rejects_crossed_market(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    payload = _payload("AAPL")
    payload[0]["asks"][0]["price"] = "99.00"
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="bid/ask geometry",
    ):
        parse_current_webull_stock_quote_v1(
            settings=settings,
            payload=payload,
            symbol="AAPL",
            received_at_utc=REGULAR + timedelta(seconds=1),
        )


def test_read_bundle_rejects_stale_quote(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(_quote("AAPL"),),
        captured_at_utc=REGULAR + timedelta(seconds=1),
    )
    path = write_current_webull_stock_quote_bundle_v1(
        settings,
        bundle,
    )
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="execution age cap",
    ):
        read_current_webull_stock_quote_bundle_v1(
            settings,
            path=path,
            now_utc=REGULAR + timedelta(seconds=31),
        )


def test_bundle_file_tamper_fails_self_fingerprint(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(_quote("AAPL"),),
        captured_at_utc=REGULAR + timedelta(seconds=1),
    )
    path = write_current_webull_stock_quote_bundle_v1(
        settings,
        bundle,
    )
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"bid_price": 100.0', '"bid_price": 101.0'), encoding="utf-8")
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="invalid",
    ):
        read_current_webull_stock_quote_bundle_v1(
            settings,
            path=path,
            now_utc=REGULAR + timedelta(seconds=2),
        )


def test_read_bundle_rejects_inconsistent_session_date(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    bad = _quote("AAPL").model_copy(
        update={"session_date": (REGULAR - timedelta(days=1)).date()}
    )
    bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(bad,),
        captured_at_utc=REGULAR + timedelta(seconds=1),
    )
    path = write_current_webull_stock_quote_bundle_v1(
        settings,
        bundle,
    )
    with pytest.raises(
        CurrentWebullStockQuoteBundleError,
        match="session date is inconsistent",
    ):
        read_current_webull_stock_quote_bundle_v1(
            settings,
            path=path,
            now_utc=REGULAR + timedelta(seconds=2),
        )
