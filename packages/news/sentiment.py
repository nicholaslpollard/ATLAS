from __future__ import annotations

from datetime import datetime
from typing import Any

from packages.schemas.case_file import EvidenceAvailability, NewsContextSummary


_SENTIMENT_SCORE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}


class Phase13NewsError(ValueError):
    pass


def _published(value: object) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise Phase13NewsError("news article is missing published_utc")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise Phase13NewsError("news published_utc must be timezone-aware")
    return parsed


def summarize_massive_news(
    articles: list[dict[str, Any]],
    *,
    ticker: str,
    cutoff_utc: datetime,
    lookback_calendar_days: int,
    snapshot_path: str | None = None,
    snapshot_sha256: str | None = None,
) -> NewsContextSummary:
    """Summarize Massive's ticker-specific article insights without generative inference."""

    symbol = ticker.strip()
    if not symbol:
        raise Phase13NewsError("ticker cannot be blank")
    if cutoff_utc.tzinfo is None:
        raise Phase13NewsError("news cutoff must be timezone-aware")

    relevant: list[tuple[datetime, dict[str, Any]]] = []
    sentiment_values: list[float] = []
    positive = neutral = negative = 0
    for article in articles:
        tickers = article.get("tickers") or []
        if symbol not in tickers:
            continue
        published = _published(article.get("published_utc"))
        if published > cutoff_utc:
            raise Phase13NewsError("provider news snapshot contains post-cutoff evidence")
        relevant.append((published, article))
        insight_value: str | None = None
        insights = article.get("insights") or []
        if isinstance(insights, list):
            for insight in insights:
                if not isinstance(insight, dict) or str(insight.get("ticker", "")) != symbol:
                    continue
                candidate = str(insight.get("sentiment", "")).strip().lower()
                if candidate in _SENTIMENT_SCORE:
                    insight_value = candidate
                    break
        if insight_value is None:
            continue
        sentiment_values.append(_SENTIMENT_SCORE[insight_value])
        if insight_value == "positive":
            positive += 1
        elif insight_value == "negative":
            negative += 1
        else:
            neutral += 1

    latest = max((item[0] for item in relevant), default=None)
    score = None if not sentiment_values else sum(sentiment_values) / len(sentiment_values)
    reasons = ["MASSIVE_PROVIDER_SENTIMENT_CONTEXT_ONLY"]
    if not relevant:
        reasons.append("NO_RECENT_TICKER_ARTICLES")
    elif not sentiment_values:
        reasons.append("RECENT_ARTICLES_WITHOUT_TICKER_SENTIMENT_CLASSIFICATION")
    else:
        reasons.append("PROVIDER_TICKER_SENTIMENT_CLASSIFICATIONS_SUMMARIZED")

    return NewsContextSummary(
        availability=EvidenceAvailability.AVAILABLE,
        cutoff_utc=cutoff_utc,
        lookback_calendar_days=lookback_calendar_days,
        article_count=len(relevant),
        positive_count=positive,
        neutral_count=neutral,
        negative_count=negative,
        sentiment_score=score,
        latest_published_utc=latest,
        provider_snapshot_path=snapshot_path,
        provider_snapshot_sha256=snapshot_sha256,
        reason_codes=tuple(reasons),
    )


def unavailable_news_context(
    *,
    cutoff_utc: datetime,
    lookback_calendar_days: int,
    reason: str,
) -> NewsContextSummary:
    return NewsContextSummary(
        availability=EvidenceAvailability.UNAVAILABLE,
        cutoff_utc=cutoff_utc,
        lookback_calendar_days=lookback_calendar_days,
        article_count=0,
        positive_count=0,
        neutral_count=0,
        negative_count=0,
        sentiment_score=None,
        reason_codes=(reason, "NEWS_CONTEXT_NOT_GUESSED"),
    )
