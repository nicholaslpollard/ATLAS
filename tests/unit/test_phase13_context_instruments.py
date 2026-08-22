from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from packages.instruments.engine import build_instrument_selection
from packages.instruments.option_filter import normalize_option_snapshot, rank_option_alternatives
from packages.news.sentiment import Phase13NewsError, summarize_massive_news
from packages.schemas.case_file import EvidenceAvailability, InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection


def _option(
    ticker: str,
    *,
    contract_type: str = "call",
    expiration: str = "2026-09-11",
    strike: float = 100.0,
    bid: float = 4.90,
    ask: float = 5.10,
    delta: float = 0.50,
    oi: int = 500,
) -> dict[str, object]:
    return {
        "details": {
            "ticker": ticker,
            "contract_type": contract_type,
            "expiration_date": expiration,
            "strike_price": strike,
        },
        "last_quote": {"bid": bid, "ask": ask, "midpoint": (bid + ask) / 2.0},
        "greeks": {"delta": delta},
        "implied_volatility": 0.35,
        "open_interest": oi,
        "day": {"volume": 100},
    }


def test_option_filter_requires_direction_dte_delta_oi_and_spread() -> None:
    as_of = date(2026, 8, 14)
    good = normalize_option_snapshot(
        _option("O:TEST260911C00100000"),
        as_of_date=as_of,
        direction=DiscoveryDirection.BULLISH,
    )
    assert good is not None and good.eligible is True

    wrong_side = normalize_option_snapshot(
        _option("O:TEST260911P00100000", contract_type="put"),
        as_of_date=as_of,
        direction=DiscoveryDirection.BULLISH,
    )
    assert wrong_side is not None and wrong_side.eligible is False
    assert "DIRECTION_ALIGNMENT_FAIL" in wrong_side.reason_codes

    wide = normalize_option_snapshot(
        _option("O:TEST260911C00105000", bid=1.0, ask=1.5),
        as_of_date=as_of,
        direction=DiscoveryDirection.BULLISH,
    )
    assert wide is not None and wide.eligible is False
    assert "SPREAD_FAIL" in wide.reason_codes


def test_option_ranking_is_supporting_only_and_deterministic() -> None:
    as_of = date(2026, 8, 14)
    items = [
        _option("O:TEST260911C00100000", bid=4.90, ask=5.10, oi=500, delta=0.50),
        _option("O:TEST260911C00105000", bid=4.95, ask=5.05, oi=200, delta=0.45),
        _option("O:TEST260911C00095000", bid=4.95, ask=5.05, oi=700, delta=0.55),
    ]
    ranked = rank_option_alternatives(
        items,
        as_of_date=as_of,
        direction=DiscoveryDirection.BULLISH,
    )
    assert ranked[0].contract_ticker == "O:TEST260911C00095000"
    selection = build_instrument_selection(
        ticker="TEST",
        as_of_date=as_of,
        direction=DiscoveryDirection.BULLISH,
        option_snapshot_items=items,
        option_snapshot_path="options.json",
        option_snapshot_sha256="a" * 64,
    )
    assert selection.primary_kind == InstrumentKind.EQUITY
    assert selection.primary_ticker == "TEST"
    assert selection.option_chain_availability == EvidenceAvailability.AVAILABLE
    assert selection.ranked_option_alternatives
    assert "OPTION_NOT_SELECTED_NO_ACCEPTED_RELATIVE_VALUE_MODEL" in selection.reason_codes


def test_news_uses_provider_ticker_sentiment_without_generative_inference() -> None:
    cutoff = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)
    articles = [
        {
            "id": "1",
            "published_utc": "2026-08-14T18:00:00Z",
            "tickers": ["TEST"],
            "insights": [{"ticker": "TEST", "sentiment": "positive", "sentiment_reasoning": "provider"}],
        },
        {
            "id": "2",
            "published_utc": "2026-08-13T18:00:00Z",
            "tickers": ["TEST"],
            "insights": [{"ticker": "TEST", "sentiment": "negative", "sentiment_reasoning": "provider"}],
        },
    ]
    result = summarize_massive_news(
        articles,
        ticker="TEST",
        cutoff_utc=cutoff,
        lookback_calendar_days=7,
    )
    assert result.availability == EvidenceAvailability.AVAILABLE
    assert result.article_count == 2
    assert result.positive_count == 1
    assert result.negative_count == 1
    assert result.sentiment_score == 0.0


def test_news_rejects_post_cutoff_evidence() -> None:
    cutoff = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)
    with pytest.raises(Phase13NewsError, match="post-cutoff"):
        summarize_massive_news(
            [
                {
                    "published_utc": "2026-08-14T20:01:00Z",
                    "tickers": ["TEST"],
                    "insights": [{"ticker": "TEST", "sentiment": "positive"}],
                }
            ],
            ticker="TEST",
            cutoff_utc=cutoff,
            lookback_calendar_days=7,
        )


def test_unavailable_option_chain_keeps_equity_primary() -> None:
    selection = build_instrument_selection(
        ticker="TEST",
        as_of_date=date(2026, 8, 14),
        direction=DiscoveryDirection.BULLISH,
        option_snapshot_items=None,
    )
    assert selection.primary_kind == InstrumentKind.EQUITY
    assert selection.option_chain_availability == EvidenceAvailability.UNAVAILABLE
    assert selection.ranked_option_alternatives == ()
