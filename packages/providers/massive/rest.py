from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from packages.core.exceptions import ProviderError
from packages.core.secrets import get_secret
from packages.core.settings import AtlasSettings


class MassiveRESTClient:
    """Minimal production REST adapter for Massive reference/current data."""

    RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}

    def __init__(self, settings: AtlasSettings, *, opener: Callable[..., Any] | None = None, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.settings = settings
        self.base_url = settings.massive.provider.rest_base_url.rstrip("/") + "/"
        self._base_host = urlsplit(self.base_url).netloc.lower()
        self._api_key = get_secret(settings.massive.credentials.api_key_env)
        self._opener = opener or urlopen
        self._sleep = sleeper
        cfg = settings.massive.reference
        self.timeout = cfg.request_timeout_seconds
        self.max_attempts = cfg.max_attempts
        self.initial_retry = cfg.initial_retry_seconds
        self.max_retry = cfg.max_retry_seconds

    @staticmethod
    def _safe_url(url: str) -> str:
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "apikey"]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    def _build_url(self, path_or_url: str, params: Mapping[str, Any] | None = None) -> str:
        if path_or_url.startswith(("http://", "https://")):
            url = self._safe_url(path_or_url)
            if urlsplit(url).netloc.lower() != self._base_host:
                raise ProviderError("Massive pagination URL changed host; refusing to forward credentials")
        else:
            url = urljoin(self.base_url, path_or_url.lstrip("/"))
        if params:
            parts = urlsplit(url)
            query = list(parse_qsl(parts.query, keep_blank_values=True))
            for key, value in params.items():
                if value is None:
                    continue
                if isinstance(value, bool):
                    value = "true" if value else "false"
                query.append((str(key), str(value)))
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        return self._safe_url(url)

    def get_json(self, path_or_url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        url = self._build_url(path_or_url, params)
        delay = self.initial_retry
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            request = Request(url, method="GET", headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json", "User-Agent": "ATLAS/0.1 reference-data"})
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ProviderError("Massive REST response root was not a JSON object")
                status = str(payload.get("status", "OK")).upper()
                if status not in {"OK", "SUCCESS"}:
                    raise ProviderError(f"Massive REST returned status {status!r}")
                return payload
            except HTTPError as exc:
                last_error = exc
                if exc.code not in self.RETRYABLE_HTTP or attempt >= self.max_attempts:
                    raise ProviderError(f"Massive REST request failed with HTTP {exc.code}") from exc
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    raise ProviderError(f"Massive REST request failed: {type(exc).__name__}") from exc
            if delay > 0:
                self._sleep(delay)
            delay = min(self.max_retry, max(delay * 2, self.initial_retry))
        raise ProviderError(f"Massive REST request failed after retries: {type(last_error).__name__}")

    def iter_pages(self, path: str, params: Mapping[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        payload = self.get_json(path, params)
        while True:
            yield payload
            next_url = payload.get("next_url")
            if not next_url:
                break
            payload = self.get_json(str(next_url))

    def list_tickers(self, *, as_of_date: str, active: bool, market: str = "stocks", limit: int | None = None) -> Iterator[dict[str, Any]]:
        params = {"market": market, "date": as_of_date, "active": active, "order": "asc", "limit": limit or self.settings.massive.reference.page_limit, "sort": "ticker"}
        for page in self.iter_pages("/v3/reference/tickers", params):
            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive All Tickers response `results` was not a list")
            for item in results:
                if isinstance(item, dict):
                    yield item

    def ticker_overview(self, ticker: str, *, as_of_date: str) -> dict[str, Any]:
        ticker = ticker.strip()
        if not ticker:
            raise ValueError("ticker cannot be blank")
        payload = self.get_json(
            f"/v3/reference/tickers/{quote(ticker, safe='')}",
            {"date": as_of_date},
        )
        result = payload.get("results")
        if not isinstance(result, dict):
            raise ProviderError("Massive Ticker Overview response `results` was not an object")
        return result

    def ticker_events(self, identifier: str) -> list[dict[str, Any]]:
        identifier = identifier.strip()
        if not identifier:
            raise ValueError("identifier cannot be blank")
        payload = self.get_json(f"/vX/reference/tickers/{identifier}/events")
        results = payload.get("results") or {}
        events = results.get("events") if isinstance(results, dict) else []
        return [item for item in (events or []) if isinstance(item, dict)]
