from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


MARKETDATA_BASE_URL = "https://api.marketdata.app/v1"
MARKETDATA_TOKEN_ENV = "MARKETDATA_TOKEN"
TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})


class MarketDataError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class MarketDataResponse:
    http_status: int
    payload: dict[str, Any]
    headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float


def _resolve_token() -> str:
    value = os.getenv(MARKETDATA_TOKEN_ENV, "").strip()
    if not value:
        raise MarketDataError(
            f"MarketData.app token is not configured in {MARKETDATA_TOKEN_ENV}"
        )
    return value


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise MarketDataError("MarketData.app response was not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise MarketDataError("MarketData.app response root was not an object")
    return value


def _retry_after(headers: dict[str, str]) -> float | None:
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    raw = lowered.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def get_json(
    path: str,
    *,
    params: dict[str, object] | None = None,
    authenticate: bool = True,
    token: str | None = None,
    timeout_seconds: float = 30.0,
    max_attempts: int = 5,
    initial_retry_seconds: float = 0.5,
    max_retry_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
) -> MarketDataResponse:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    query = urllib.parse.urlencode(
        [(str(k), str(v)) for k, v in (params or {}).items() if v is not None]
    )
    url = MARKETDATA_BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query

    headers = {
        "Accept": "application/json",
        "User-Agent": "ATLAS-marketdata-options-qualification-v1/1",
    }
    if authenticate:
        headers["Authorization"] = f"Bearer {(token or _resolve_token()).strip()}"

    started = time.perf_counter()
    last_error: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
                status = int(response.status)
                if status not in {200, 203}:
                    raise MarketDataError(
                        f"MarketData.app unexpected success status {status}",
                        http_status=status,
                    )
                return MarketDataResponse(
                    http_status=status,
                    payload=_decode_json(raw),
                    headers={str(k): str(v) for k, v in response.headers.items()},
                    response_bytes=len(raw),
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            payload: dict[str, Any] = {}
            try:
                payload = _decode_json(raw) if raw else {}
            except MarketDataError:
                pass
            error_code = str(
                payload.get("s")
                or payload.get("errmsg")
                or payload.get("error")
                or "http_error"
            )

            if exc.code == 404:
                return MarketDataResponse(
                    http_status=404,
                    payload=payload,
                    headers={str(k): str(v) for k, v in exc.headers.items()},
                    response_bytes=len(raw),
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                )

            if exc.code in {400, 401, 402, 403}:
                raise MarketDataError(
                    f"MarketData.app HTTP {exc.code}: {error_code}",
                    http_status=int(exc.code),
                    error_code=error_code,
                ) from exc

            last_error = exc
            if exc.code in TRANSIENT_STATUS and attempt < max_attempts:
                retry_after = _retry_after(
                    {str(k): str(v) for k, v in exc.headers.items()}
                )
                delay = (
                    retry_after
                    if retry_after is not None
                    else min(
                        initial_retry_seconds * (2 ** (attempt - 1)),
                        max_retry_seconds,
                    )
                )
                sleep(delay)
                continue

            raise MarketDataError(
                f"MarketData.app HTTP {exc.code}: {error_code}",
                http_status=int(exc.code),
                error_code=error_code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < max_attempts:
                sleep(
                    min(
                        initial_retry_seconds * (2 ** (attempt - 1)),
                        max_retry_seconds,
                    )
                )
                continue
            break

    raise MarketDataError(
        f"MarketData.app request failed after {max_attempts} attempts: "
        f"{type(last_error).__name__ if last_error else 'unknown error'}"
    ) from last_error


def array_rows(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if payload.get("s") != "ok":
        return ()
    array_keys = [
        key
        for key, value in payload.items()
        if key != "s" and isinstance(value, list)
    ]
    if not array_keys:
        return ()
    lengths = {len(payload[key]) for key in array_keys}
    if len(lengths) != 1:
        raise MarketDataError(
            "MarketData.app array-keyed response has inconsistent column lengths"
        )
    count = lengths.pop()
    return tuple(
        {key: payload[key][index] for key in array_keys}
        for index in range(count)
    )


def historical_chain(
    underlying: str,
    *,
    date: str,
    dte: int = 30,
    strike_limit: int = 8,
    side: str | None = None,
) -> MarketDataResponse:
    return get_json(
        f"options/chain/{underlying.upper()}/",
        params={
            "date": date,
            "dte": dte,
            "strikeLimit": strike_limit,
            "side": side,
        },
    )


def historical_quote_series(
    option_symbol: str,
    *,
    from_date: str,
    to_date: str,
) -> MarketDataResponse:
    return get_json(
        f"options/quotes/{option_symbol}/",
        params={"from": from_date, "to": to_date},
    )
