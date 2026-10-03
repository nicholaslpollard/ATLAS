from __future__ import annotations

"""Minimal read-only client for a local ThetaData v3 Terminal.

ThetaData's v3 REST API is served by the locally running Theta Terminal. This
client deliberately permits loopback hosts only and exposes no provider write path.
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
NO_DATA_STATUS = 472
TRANSIENT_STATUS = frozenset({429, 474, 571, 572, 500, 502, 503, 504})
PERMANENT_STATUS = frozenset({
    400, 401, 402, 403, 404, 405, 409, 422,
    470, 471, 473, 475, 476, 477, 478, 570,
})


class ThetaDataError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None) -> None:
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
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or not parsed.port
    ):
        raise ThetaDataError(
            f"{THETADATA_BASE_URL_ENV} must point to a local http Theta Terminal with port"
        )
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
    timeout_seconds: float = 60.0,
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
        "User-Agent": "ATLAS-thetadata-candidate-surface-v1/1",
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
            if exc.code == NO_DATA_STATUS:
                return ThetaDataResponse(
                    http_status=int(exc.code),
                    rows=(),
                    headers={str(k): str(v) for k, v in exc.headers.items()},
                    response_bytes=len(body),
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                    raw_body=body,
                )
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


def option_at_time_quote_surface(
    *,
    symbol: str,
    date_et: str,
    time_of_day_et: str,
    right: str = "call",
    max_dte: int = 75,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    """Return a provider-side option surface at one decision clock.

    No strike or expiration is preselected. The optional strike_range is intentionally
    left unset by the current research plan so contract eligibility can be decided
    downstream from observed causal evidence.
    """
    if max_dte < 1:
        raise ValueError("max_dte must be positive")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    return get_json(
        "/v3/option/at_time/quote",
        params={
            "symbol": symbol,
            "expiration": "*",
            "strike": "*",
            "right": right,
            "start_date": date_et.replace("-", ""),
            "end_date": date_et.replace("-", ""),
            "time_of_day": time_of_day_et,
            "max_dte": max_dte,
            "strike_range": strike_range,
            "format": "json",
        },
    )


def option_at_time_quote(
    *,
    symbol: str,
    expiration: str,
    strike: str,
    right: str,
    date_et: str,
    time_of_day_et: str,
) -> ThetaDataResponse:
    """Exact-contract at-time quote reserved for the later selected-contract exit stage."""
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


def option_history_open_interest_surface(
    *,
    symbol: str,
    date_et: str,
    right: str = "call",
    max_dte: int = 75,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    """Historical previous-session open interest for a bounded option surface."""
    if max_dte < 1:
        raise ValueError("max_dte must be positive")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    return get_json(
        "/v3/option/history/open_interest",
        params={
            "symbol": symbol,
            "expiration": "*",
            "strike": "*",
            "right": right,
            "date": date_et.replace("-", ""),
            "max_dte": max_dte,
            "strike_range": strike_range,
            "format": "json",
        },
    )


def option_history_binomial_first_order_greeks_at_minute(
    *,
    symbol: str,
    expiration: str,
    date_et: str,
    right: str = "call",
    time_of_day_et: str = "09:35:00.000",
    annual_dividend: float,
    rate_type: str = "sofr",
    version: str = "1",
    binomial_steps: int = 101,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    """Dividend-aware American-style first-order Greeks at one historical minute.

    This endpoint is intentionally expiration-specific. The upstream quote/open-
    interest stage must first narrow the candidate expirations. ATLAS requires an
    explicit annual dividend amount; unknown dividend context is not silently treated
    as zero.
    """
    if annual_dividend < 0:
        raise ValueError("annual_dividend cannot be negative")
    if binomial_steps < 5 or binomial_steps > 201:
        raise ValueError("binomial_steps must be in [5, 201]")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    if version not in {"1", "latest"}:
        raise ValueError("unsupported ThetaData Greeks version")
    return get_json(
        "/v3/option/history/binomial_greeks/first_order",
        params={
            "symbol": symbol,
            "expiration": expiration.replace("-", ""),
            "strike": "*",
            "right": right,
            "date": date_et.replace("-", ""),
            "start_time": time_of_day_et,
            "end_time": time_of_day_et,
            "interval": "1m",
            "annual_dividend": annual_dividend,
            "rate_type": rate_type,
            "version": version,
            "binomial_steps": binomial_steps,
            "strike_range": strike_range,
            "format": "json",
        },
    )
