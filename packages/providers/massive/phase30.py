from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from packages.core.exceptions import ProviderError

from .rest import MassiveRESTClient


PHASE30_NEWS_ENDPOINT = "/v2/reference/news"
PHASE30_NEWS_SORT_FIELD = "published_utc"
PHASE30_NEWS_ORDER = "asc"
PHASE30_NEWS_PAGE_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class Phase30NewsWindowResult:
    articles: tuple[dict[str, Any], ...]
    page_count: int
    request_ids: tuple[str, ...]


def parse_news_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ProviderError("Massive news article is missing published_utc")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ProviderError(f"Massive news published_utc is not RFC3339-compatible: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ProviderError("Massive news published_utc must be timezone-aware")
    return parsed.astimezone(UTC)


def _utc_bound(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def validate_news_article(
    item: dict[str, Any], *, start_utc: datetime, end_utc: datetime
) -> None:
    article_id = item.get("id")
    if not isinstance(article_id, str) or not article_id.strip():
        raise ProviderError("Massive news article is missing a nonblank id")

    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ProviderError(f"Massive news article {article_id!r} is missing a nonblank title")

    published = parse_news_timestamp(item.get("published_utc"))
    if published < start_utc or published > end_utc:
        raise ProviderError(
            f"Massive news article {article_id!r} publication timestamp is outside the requested window"
        )

    tickers = item.get("tickers")
    if not isinstance(tickers, list):
        raise ProviderError(f"Massive news article {article_id!r} tickers must be a list")
    for ticker in tickers:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ProviderError(
                f"Massive news article {article_id!r} contains an invalid ticker association"
            )


class MassivePhase30NewsClient:
    """Historical financial-news adapter for Phase30 feasibility/provenance only.

    This class deliberately reuses the accepted Massive REST authority. It performs
    read-only GET pagination and preserves provider article objects and ticker text.
    No market outcomes, return data, model fitting, or trading authority live here.
    """

    def __init__(self, rest: MassiveRESTClient) -> None:
        self.rest = rest

    def news_window(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
    ) -> Phase30NewsWindowResult:
        start = _utc_bound(start_utc, label="start_utc")
        end = _utc_bound(end_utc, label="end_utc")
        if start > end:
            raise ValueError("start_utc must be <= end_utc")

        params = {
            "published_utc.gte": _rfc3339(start),
            "published_utc.lte": _rfc3339(end),
            "order": PHASE30_NEWS_ORDER,
            "sort": PHASE30_NEWS_SORT_FIELD,
            "limit": PHASE30_NEWS_PAGE_LIMIT,
        }

        by_id: dict[str, dict[str, Any]] = {}
        page_count = 0
        request_ids: list[str] = []
        for page in self.rest.iter_pages(PHASE30_NEWS_ENDPOINT, params):
            page_count += 1
            request_id = page.get("request_id")
            if request_id is not None:
                if not isinstance(request_id, str) or not request_id.strip():
                    raise ProviderError("Massive news request_id must be a nonblank string when present")
                request_ids.append(request_id)

            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive news response results must be a list")
            for raw in results:
                if not isinstance(raw, dict):
                    raise ProviderError("Massive news result must be an object")
                item = dict(raw)
                validate_news_article(item, start_utc=start, end_utc=end)
                article_id = str(item["id"])
                existing = by_id.get(article_id)
                if existing is not None and existing != item:
                    raise ProviderError(
                        f"Massive news returned conflicting payloads for article id {article_id!r}"
                    )
                by_id[article_id] = item

        articles = tuple(
            sorted(
                by_id.values(),
                key=lambda item: (parse_news_timestamp(item["published_utc"]), str(item["id"])),
            )
        )
        return Phase30NewsWindowResult(
            articles=articles,
            page_count=page_count,
            request_ids=tuple(request_ids),
        )
