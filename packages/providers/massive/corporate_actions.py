from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.providers.massive.rest import MassiveRESTClient


MASSIVE_SPLITS_ENDPOINT = "/stocks/v1/splits"
MASSIVE_SPLITS_PAGE_LIMIT = 5000


class MassiveCorporateActionsProvider:
    """Small evidence adapter for Massive stock corporate-action reference data."""

    def __init__(
        self,
        settings: AtlasSettings | None = None,
        *,
        client: MassiveRESTClient | Any | None = None,
    ) -> None:
        if client is None:
            if settings is None:
                raise ValueError("settings are required when no REST client is supplied")
            client = MassiveRESTClient(settings)
        self.client = client

    def splits(self, *, start_date: date, end_date: date) -> Iterator[dict[str, Any]]:
        if end_date < start_date:
            raise ValueError("split end_date precedes start_date")
        params = {
            "execution_date.gte": start_date.isoformat(),
            "execution_date.lte": end_date.isoformat(),
            "limit": MASSIVE_SPLITS_PAGE_LIMIT,
            "sort": "execution_date.asc",
        }
        for page in self.client.iter_pages(MASSIVE_SPLITS_ENDPOINT, params):
            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive Splits response `results` was not a list")
            for item in results:
                if isinstance(item, dict):
                    yield item
