from __future__ import annotations

"""Minimal read-only client for a local ThetaData v3 Terminal.

ThetaData's v3 REST API is served by the locally running Theta Terminal. This
client deliberately permits loopback hosts only. It has no provider write path.
"""

from dataclasses import dataclass
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


THETADATA_BASE_URL_ENV = "THETADATA_BASE_URL"
DEFAULT_THETADATA_BASE_URL = "http://127.0.0.1:25503"
TRANSIENT_STATUS = frozenset({500, 502, 503, 504})


class ThetaDataError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class ThetaDataResponse:
    http_status: int
    rows: tuple[dict[str, Any], ...]
    headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float
    raw_body: bytes


def _base_url() -> str:
    raw = os.getenv(THETADATA_BASE_URL_ENV, DEFAULT_THETADATA_BASE_URL).strip()
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ThetaDataError(
            f"{THETADATA_BASE_URL_ENV} must point to a local http Theta Terminal"
        )
    if not parsed.port:
        raise ThetaDataError(f"{THETADATA_BASE_URL_ENV} must include the terminal port")
    return raw.rstrip("/")


def _decode_rows(raw: bytes) -> tuple[dict[str, Any], ...]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ThetaDataError("ThetaData response was not valid UTF-8 JSON") from exc
    if not isinstance(value, list):
        raise ThetaDataError("ThetaData v3 JSON response root was not an array")
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ThetaDataError("ThetaData v3 JSON response row was not an object")
        rows.append(dict(item))
    return tuple(rows)


def get_json(
    path: str,
    *,
    params: dict[str, object],
    timeout_seconds: float = 45.0,
    max_attempts: int = 4,
    initial_retry_seconds: float = 0.5,
    max_retry_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ThetaDataResponse:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    query_params = [
        (str(key), str(value))
        for key, value in params.items()
        if value is not None
    ]
    if not any(key == "format" for key, _ in query_params):
        query_params.append(("format", "json"))
    query = urllib.parse.urlencode(query_params)
    url = _base_url() + "/" + path.lstrip("/")
    if query:
        url += "?" + query
    headers = {
        "Accept": "application/json",
        "User-Agent": "ATLAS-thetadata-intraday-qualification-v1/1",
    }

    started = time.perf_counter()
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
                status = int(response.status)
                if status != 200:
                    raise ThetaDataError(
                        f"ThetaData unexpected success status {status}",
                        http_status=status,
                    )
                return ThetaDataResponse(
                    http_status=status,
                    rows=_decode_rows(raw),
                    headers={str(k): str(v) for k, v in response.headers.items()},
                    response_bytes=len(raw),
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                    raw_body=raw,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read()
            message = body.decode("utf-8", errors="replace").strip()
            if exc.code in {400, 401, 402, 403, 404, 405, 409, 422, 429}:
                raise ThetaDataError(
                    f"ThetaData HTTP {exc.code}: {message[:500]}",
                    http_status=int(exc.code),
                ) from exc
            last_error = exc
            if exc.code in TRANSIENT_STATUS and attempt < max_attempts:
                sleep(min(initial_retry_seconds * (2 ** (attempt - 1)), max_retry_seconds))
                continue
            raise ThetaDataError(
                f"ThetaData HTTP {exc.code}: {message[:500]}",
                http_status=int(exc.code),
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < max_attempts:
                sleep(min(initial_retry_seconds * (2 ** (attempt - 1)), max_retry_seconds))
                continue
            break
    raise ThetaDataError(
        f"ThetaData request failed after {max_attempts} attempts: "
        f"{type(last_error).__name__ if last_error else 'unknown error'}"
    ) from last_error


def option_at_time_quote(
    *,
    symbol: str,
    expiration: str,
    strike: str,
    right: str,
    date_et: str,
    time_of_day_et: str,
) -> ThetaDataResponse:
    return get_json(
        "/v3/option/at_time/quote",
        params={
            "symbol": symbol,
            "expiration": expiration.replace("-", ""),
            "strike": strike,
            "right": right,
            "start_date": date_et.replace("-", ""),
            "end_date": date_et.replace("-", ""),
            "time_of_day": time_of_day_et,
            "format": "json",
        },
    )
