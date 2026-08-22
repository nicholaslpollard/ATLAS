from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from packages.portfolio.phase13_policy import (
    PHASE13_NEWS_MAX_ARTICLES,
    PHASE13_OPTION_MAX_DTE,
    PHASE13_OPTION_MIN_DTE,
)
from packages.providers.massive.rest import MassiveRESTClient


class MassivePhase13ResearchClient:
    """Read-only Massive adapters used only after a Phase 12 research case exists."""

    def __init__(self, rest: MassiveRESTClient) -> None:
        self.rest = rest

    def news(
        self,
        ticker: str,
        *,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[dict[str, Any]]:
        symbol = ticker.strip()
        if not symbol:
            raise ValueError("ticker cannot be blank")
        results: list[dict[str, Any]] = []
        params = {
            "ticker": symbol,
            "published_utc.gte": start_utc.isoformat().replace("+00:00", "Z"),
            "published_utc.lte": end_utc.isoformat().replace("+00:00", "Z"),
            "order": "desc",
            "sort": "published_utc",
            "limit": min(1000, PHASE13_NEWS_MAX_ARTICLES),
        }
        for page in self.rest.iter_pages("/v2/reference/news", params):
            page_results = page.get("results") or []
            if not isinstance(page_results, list):
                raise ValueError("Massive news results must be a list")
            for item in page_results:
                if isinstance(item, dict):
                    results.append(item)
                    if len(results) >= PHASE13_NEWS_MAX_ARTICLES:
                        return results
        return results

    def option_chain(self, ticker: str, *, as_of_date: date) -> Iterator[dict[str, Any]]:
        symbol = ticker.strip()
        if not symbol:
            raise ValueError("ticker cannot be blank")
        expiration_min = as_of_date + timedelta(days=PHASE13_OPTION_MIN_DTE)
        expiration_max = as_of_date + timedelta(days=PHASE13_OPTION_MAX_DTE)
        params = {
            "expiration_date.gte": expiration_min.isoformat(),
            "expiration_date.lte": expiration_max.isoformat(),
            "order": "asc",
            "sort": "ticker",
            "limit": 250,
        }
        path = f"/v3/snapshot/options/{quote(symbol, safe='')}"
        for page in self.rest.iter_pages(path, params):
            page_results = page.get("results") or []
            if not isinstance(page_results, list):
                raise ValueError("Massive option-chain results must be a list")
            for item in page_results:
                if isinstance(item, dict):
                    yield item
