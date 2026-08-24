from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from packages.core.enums import SessionSegment
from packages.core.settings import load_settings
from packages.execution.phase18_webull_quote import (
    Phase18WebullQuoteEvidence,
    Phase18WebullQuoteResolver,
)
from packages.execution.quote_source import ExecutionQuoteError


ROOT = Path(__file__).resolve().parents[2]
REGULAR = datetime(2026, 8, 24, 15, 0, 0, tzinfo=UTC)


def _settings():
    return load_settings(ROOT)


def _evidence(
    *,
    symbol: str = "AAPL",
    provider_time: datetime = REGULAR,
    received_time: datetime | None = None,
    segment: SessionSegment = SessionSegment.REGULAR,
) -> Phase18WebullQuoteEvidence:
    return Phase18WebullQuoteEvidence(
        symbol=symbol,
        provider_timestamp_utc=provider_time,
        received_at_utc=received_time or provider_time,
        session_date=date(2026, 8, 24),
        session_segment=segment,
        bid_price=100.0,
        bid_size=10,
        ask_price=100.1,
        ask_size=12,
    )


def _write(path: Path, evidence: Phase18WebullQuoteEvidence) -> None:
    path.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")


def test_webull_quote_resolver_accepts_fresh_regular_exact_ticker(tmp_path: Path) -> None:
    path = tmp_path / "quote.json"
    _write(path, _evidence())
    quote = Phase18WebullQuoteResolver(_settings(), path=path).quote(
        "AAPL", now_utc=REGULAR + timedelta(seconds=10)
    )
    assert quote.symbol == "AAPL"
    assert quote.bid_price == 100.0
    assert quote.ask_price == 100.1


def test_webull_quote_resolver_rejects_stale_provider_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "quote.json"
    _write(path, _evidence())
    with pytest.raises(ExecutionQuoteError, match="execution age cap"):
        Phase18WebullQuoteResolver(_settings(), path=path).quote(
            "AAPL", now_utc=REGULAR + timedelta(seconds=31)
        )


def test_webull_quote_resolver_rejects_premarket_even_when_fresh(tmp_path: Path) -> None:
    path = tmp_path / "quote.json"
    premarket = datetime(2026, 8, 24, 13, 15, 0, tzinfo=UTC)
    _write(
        path,
        _evidence(
            provider_time=premarket,
            received_time=premarket,
            segment=SessionSegment.PREMARKET,
        ),
    )
    with pytest.raises(ExecutionQuoteError, match="outside regular session"):
        Phase18WebullQuoteResolver(_settings(), path=path).quote(
            "AAPL", now_utc=premarket + timedelta(seconds=5)
        )


def test_webull_quote_resolver_preserves_exact_provider_ticker_case(tmp_path: Path) -> None:
    path = tmp_path / "quote.json"
    _write(path, _evidence(symbol="AaPL"))
    with pytest.raises(ExecutionQuoteError, match="exact provider-native ticker"):
        Phase18WebullQuoteResolver(_settings(), path=path).quote(
            "AAPL", now_utc=REGULAR + timedelta(seconds=5)
        )


def test_webull_quote_evidence_forbids_any_write_claim() -> None:
    with pytest.raises(ValueError, match="cannot contain provider/broker writes"):
        Phase18WebullQuoteEvidence(
            symbol="AAPL",
            provider_timestamp_utc=REGULAR,
            received_at_utc=REGULAR,
            session_date=date(2026, 8, 24),
            session_segment=SessionSegment.REGULAR,
            bid_price=100.0,
            ask_price=100.1,
            provider_writes=1,
        )
