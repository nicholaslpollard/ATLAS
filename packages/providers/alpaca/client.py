from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from packages.core.settings import AtlasSettings


@dataclass(frozen=True, slots=True)
class AlpacaCredentialProfile:
    name: str
    api_key: str
    api_secret: str
    trading_base_url: str


@dataclass(frozen=True, slots=True)
class AlpacaApiPage:
    request_name: str
    url: str
    http_status: int
    raw_body: bytes
    payload: Any
    response_headers: dict[str, str]
    page_token_used: str | None = None
    next_page_token: str | None = None


class AlpacaMarketDataClient:
    """Small dependency-free Alpaca client for deterministic historical backfill work.

    Credentials are read from environment variables named in config. They are sent only
    as request headers and are never included in URLs, reprs, persisted payload metadata,
    or exception messages.
    """

    def __init__(self, settings: AtlasSettings, *, sleeper=time.sleep) -> None:
        self.settings = settings
        self.cfg = settings.alpaca.market_data
        self.profile = self._resolve_profile()
        self.sleeper = sleeper

    def _resolve_profile(self) -> AlpacaCredentialProfile:
        cfg = self.settings.alpaca.credentials
        order = (cfg.preferred_profile, "live" if cfg.preferred_profile == "paper" else "paper")
        for name in order:
            if name == "paper":
                key = os.getenv(cfg.paper_api_key_env, "").strip()
                secret = os.getenv(cfg.paper_api_secret_env, "").strip()
                endpoint = os.getenv(cfg.paper_endpoint_env, "https://paper-api.alpaca.markets/v2").strip()
            elif name == "live":
                key = os.getenv(cfg.live_api_key_env, "").strip()
                secret = os.getenv(cfg.live_api_secret_env, "").strip()
                endpoint = os.getenv(cfg.live_endpoint_env, "https://api.alpaca.markets").strip()
            else:
                continue
            if key and secret:
                return AlpacaCredentialProfile(
                    name=name,
                    api_key=key,
                    api_secret=secret,
                    trading_base_url=endpoint.rstrip("/"),
                )
        raise RuntimeError("Alpaca backfill requires a configured paper or live API key/secret pair")

    @property
    def credential_profile_name(self) -> str:
        return self.profile.name

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.profile.api_key,
            "APCA-API-SECRET-KEY": self.profile.api_secret,
            "Accept": "application/json",
            "User-Agent": "ATLAS-historical-backfill/1",
        }

    @staticmethod
    def _decode_json(body: bytes) -> Any:
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Alpaca returned a non-JSON response") from exc

    def _request_json(
        self,
        *,
        request_name: str,
        base_url: str,
        path: str,
        params: dict[str, object] | None = None,
        page_token_used: str | None = None,
    ) -> AlpacaApiPage:
        query = urlencode(
            [(key, str(value)) for key, value in (params or {}).items() if value is not None]
        )
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        last_error: Exception | None = None
        for attempt in range(1, self.cfg.max_attempts + 1):
            request = Request(url, headers=self._headers(), method="GET")
            try:
                with urlopen(request, timeout=self.cfg.request_timeout_seconds) as response:
                    body = response.read()
                    status = int(response.status)
                    headers = {str(k): str(v) for k, v in response.headers.items()}
                payload = self._decode_json(body)
                next_token = payload.get("next_page_token") if isinstance(payload, dict) else None
                return AlpacaApiPage(
                    request_name=request_name,
                    url=url,
                    http_status=status,
                    raw_body=body,
                    payload=payload,
                    response_headers=headers,
                    page_token_used=page_token_used,
                    next_page_token=str(next_token) if next_token else None,
                )
            except HTTPError as exc:
                body = exc.read()
                status = int(exc.code)
                if status in {401, 403}:
                    raise RuntimeError(f"Alpaca {request_name} access denied with HTTP {status}") from exc
                last_error = exc
                if status != 429 and status < 500:
                    message = None
                    try:
                        payload = self._decode_json(body)
                        if isinstance(payload, dict):
                            message = payload.get("message")
                    except RuntimeError:
                        pass
                    suffix = f": {message}" if message else ""
                    raise RuntimeError(f"Alpaca {request_name} failed with HTTP {status}{suffix}") from exc
                if attempt < self.cfg.max_attempts:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.replace(".", "", 1).isdigit()
                        else min(
                            self.cfg.initial_retry_seconds * (2 ** (attempt - 1)),
                            self.cfg.max_retry_seconds,
                        )
                    )
                    self.sleeper(delay)
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.cfg.max_attempts:
                    delay = min(
                        self.cfg.initial_retry_seconds * (2 ** (attempt - 1)),
                        self.cfg.max_retry_seconds,
                    )
                    self.sleeper(delay)

        raise RuntimeError(
            f"Alpaca {request_name} failed after {self.cfg.max_attempts} attempts: "
            f"{type(last_error).__name__ if last_error else 'unknown error'}"
        ) from last_error

    def get_assets(self, *, status: str) -> AlpacaApiPage:
        # The user's paper endpoint is normally configured with a trailing /v2 while
        # the live endpoint may be the host root. Normalize both to one /v2/assets URL.
        base = self.profile.trading_base_url
        if base.endswith("/v2"):
            path = "assets"
        else:
            path = "v2/assets"
        return self._request_json(
            request_name=f"assets_{status}",
            base_url=base,
            path=path,
            params={"status": status, "asset_class": "us_equity"},
        )

    def corporate_action_pages(self, *, start: str, end: str) -> Iterator[AlpacaApiPage]:
        token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            page = self._request_json(
                request_name="corporate_actions",
                base_url=self.cfg.base_url,
                path="v1/corporate-actions",
                params={
                    "start": start,
                    "end": end,
                    "region": "us",
                    "data_quality": "complete",
                    "limit": 1000,
                    "sort": "asc",
                    "page_token": token,
                },
                page_token_used=token,
            )
            yield page
            token = page.next_page_token
            if not token:
                break
            if token in seen_tokens:
                raise RuntimeError("Alpaca corporate-action pagination repeated a page token")
            seen_tokens.add(token)

    def historical_bar_pages(
        self,
        *,
        symbols: list[str] | tuple[str, ...],
        start: str,
        end: str,
    ) -> Iterator[AlpacaApiPage]:
        clean = tuple(dict.fromkeys(str(symbol).strip() for symbol in symbols if str(symbol).strip()))
        if not clean:
            raise ValueError("historical bars require at least one symbol")
        if len(clean) > self.cfg.symbol_batch_size:
            raise ValueError(
                f"historical bar batch exceeds configured symbol_batch_size={self.cfg.symbol_batch_size}"
            )

        token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            page = self._request_json(
                request_name="historical_bars",
                base_url=self.cfg.base_url,
                path="v2/stocks/bars",
                params={
                    "symbols": ",".join(clean),
                    "timeframe": self.cfg.timeframe,
                    "start": start,
                    "end": end,
                    "limit": self.cfg.page_limit,
                    "adjustment": self.cfg.adjustment,
                    "feed": self.cfg.feed,
                    "asof": self.cfg.asof,
                    "sort": "asc",
                    "page_token": token,
                },
                page_token_used=token,
            )
            yield page
            token = page.next_page_token
            if not token:
                break
            if token in seen_tokens:
                raise RuntimeError("Alpaca historical-bar pagination repeated a page token")
            seen_tokens.add(token)
