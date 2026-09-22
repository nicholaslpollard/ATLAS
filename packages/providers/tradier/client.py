from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from packages.core.settings import AtlasSettings


@dataclass(frozen=True, slots=True)
class TradierApiResponse:
    request_name: str
    url: str
    http_status: int
    payload: Any
    response_headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class TradierQuoteBatch:
    requested_symbols: tuple[str, ...]
    returned_rows: tuple[dict[str, Any], ...]
    response: TradierApiResponse

    @property
    def returned_symbols(self) -> tuple[str, ...]:
        values = {
            str(row.get("symbol") or "").strip()
            for row in self.returned_rows
            if str(row.get("symbol") or "").strip()
        }
        return tuple(sorted(values))


class TradierMarketDataClient:
    """Read-only Tradier production market-data client for source qualification.

    The token is read from the configured environment variable, used only in the
    Authorization header, and is never persisted, returned, included in URLs, or
    exposed through repr output. This client intentionally contains no order/account
    mutation methods and creates no PAPER/LIVE trading authority.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        sleeper=time.sleep,
        monotonic=time.monotonic,
    ) -> None:
        self.settings = settings
        self.cfg = settings.tradier.market_data
        self.provider = settings.tradier.provider
        self._api_key = self._resolve_api_key()
        self.sleeper = sleeper
        self.monotonic = monotonic
        self._last_request_started_at: float | None = None

    def _resolve_api_key(self) -> str:
        env_name = self.settings.tradier.credentials.api_key_env
        value = os.getenv(env_name, "").strip()
        if not value:
            raise RuntimeError(
                f"Tradier source qualification requires {env_name} in the local environment"
            )
        return value

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "ATLAS-tradier-source-qualification/1",
        }

    @staticmethod
    def _decode_json(body: bytes) -> Any:
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Tradier returned a non-JSON response") from exc

    def _pace(self) -> None:
        interval = 60.0 / float(self.cfg.requests_per_minute)
        now = self.monotonic()
        if self._last_request_started_at is not None:
            remaining = interval - (now - self._last_request_started_at)
            if remaining > 0:
                self.sleeper(remaining)
                now = self.monotonic()
        self._last_request_started_at = now

    def _request_json(
        self,
        *,
        request_name: str,
        path: str,
        method: str = "GET",
        params: dict[str, object] | None = None,
        form: dict[str, object] | None = None,
    ) -> TradierApiResponse:
        base = self.provider.production_base_url.rstrip("/")
        url = f"{base}/{path.lstrip('/')}"
        query = urlencode(
            [(key, str(value)) for key, value in (params or {}).items() if value is not None]
        )
        if query:
            url = f"{url}?{query}"

        data = None
        headers = self._headers()
        if form is not None:
            data = urlencode(
                [(key, str(value)) for key, value in form.items() if value is not None]
            ).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        last_error: Exception | None = None
        for attempt in range(1, self.cfg.max_attempts + 1):
            self._pace()
            started = self.monotonic()
            request = Request(url, data=data, headers=headers, method=method)
            try:
                with urlopen(request, timeout=self.cfg.request_timeout_seconds) as response:
                    body = response.read()
                    status = int(response.status)
                    response_headers = {
                        str(key): str(value) for key, value in response.headers.items()
                    }
                return TradierApiResponse(
                    request_name=request_name,
                    url=url,
                    http_status=status,
                    payload=self._decode_json(body),
                    response_headers=response_headers,
                    response_bytes=len(body),
                    elapsed_seconds=max(0.0, self.monotonic() - started),
                )
            except HTTPError as exc:
                body = exc.read()
                status = int(exc.code)
                last_error = exc
                if status in {401, 403}:
                    raise RuntimeError(
                        f"Tradier {request_name} access denied with HTTP {status}"
                    ) from exc
                if status != 429 and status < 500:
                    message = ""
                    try:
                        payload = self._decode_json(body)
                        if isinstance(payload, dict):
                            errors = payload.get("errors")
                            message = f": {errors}" if errors else ""
                    except RuntimeError:
                        pass
                    raise RuntimeError(
                        f"Tradier {request_name} failed with HTTP {status}{message}"
                    ) from exc
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
            f"Tradier {request_name} failed after {self.cfg.max_attempts} attempts: "
            f"{type(last_error).__name__ if last_error else 'unknown error'}"
        ) from last_error

    @staticmethod
    def _quote_rows(payload: Any) -> tuple[dict[str, Any], ...]:
        if not isinstance(payload, dict):
            raise RuntimeError("Tradier quotes payload is not an object")
        quotes = payload.get("quotes")
        if not isinstance(quotes, dict):
            raise RuntimeError("Tradier quotes payload is missing quotes object")
        rows = quotes.get("quote")
        if rows is None:
            return ()
        if isinstance(rows, dict):
            return (dict(rows),)
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return tuple(dict(item) for item in rows)
        raise RuntimeError("Tradier quotes.quote is neither an object nor list of objects")

    def post_quotes(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        greeks: bool = False,
        include_lot_size: bool = False,
    ) -> TradierQuoteBatch:
        clean = tuple(
            dict.fromkeys(str(symbol).strip() for symbol in symbols if str(symbol).strip())
        )
        if not clean:
            raise ValueError("Tradier quote request requires at least one symbol")
        response = self._request_json(
            request_name="post_quotes",
            path="markets/quotes",
            method="POST",
            form={
                "symbols": ",".join(clean),
                "greeks": str(bool(greeks)).lower(),
                "includeLotSize": str(bool(include_lot_size)).lower(),
            },
        )
        return TradierQuoteBatch(
            requested_symbols=clean,
            returned_rows=self._quote_rows(response.payload),
            response=response,
        )

    def create_market_stream_session(self) -> TradierApiResponse:
        return self._request_json(
            request_name="create_market_stream_session",
            path="markets/events/session",
            method="POST",
            form={},
        )
