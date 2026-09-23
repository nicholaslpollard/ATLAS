from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


CZAR28_BASE_URL = "https://czar28.com/v1"
CZAR28_CREDENTIAL_ENV = "CZAR_API_KEY"
CZAR28_TRANSIENT_HTTP_STATUS = frozenset({500, 502, 503, 504})
CZAR28_DEFAULT_MAX_ATTEMPTS = 5
CZAR28_DEFAULT_INITIAL_RETRY_SECONDS = 0.25
CZAR28_DEFAULT_MAX_RETRY_SECONDS = 2.0


class Czar28Error(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        transport_attempts: int = 0,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.transport_attempts = max(0, int(transport_attempts))
        self.http_status = http_status
        self.error_code = error_code


class Czar28QuotaExhausted(Czar28Error):
    pass


@dataclass(frozen=True, slots=True)
class Czar28Response:
    http_status: int
    payload: dict[str, Any]
    headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float
    transport_attempts: int = 1


def _resolve_api_key() -> str:
    value = os.getenv(CZAR28_CREDENTIAL_ENV, "").strip()
    if not value:
        raise Czar28Error(
            f"Czar28 API key is not configured in {CZAR28_CREDENTIAL_ENV}"
        )
    return value


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Czar28Error("Czar28 response was not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise Czar28Error("Czar28 response root was not an object")
    return value


def _safe_decode_json(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return _decode_json(raw)
    except Czar28Error:
        return {"raw_error": raw[:500].decode("utf-8", errors="replace")}


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    raw = lowered.get("retry-after")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return max(0.0, value)


def get_json(
    path: str,
    *,
    params: dict[str, object] | None = None,
    idempotency_key: str | None = None,
    timeout_seconds: float = 30.0,
    api_key: str | None = None,
    authenticate: bool = True,
    max_attempts: int = CZAR28_DEFAULT_MAX_ATTEMPTS,
    initial_retry_seconds: float = CZAR28_DEFAULT_INITIAL_RETRY_SECONDS,
    max_retry_seconds: float = CZAR28_DEFAULT_MAX_RETRY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Czar28Response:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if initial_retry_seconds < 0 or max_retry_seconds < 0:
        raise ValueError("retry delays must be non-negative")

    key = ""
    if authenticate:
        key = (api_key or _resolve_api_key()).strip()

    query = urllib.parse.urlencode(
        {str(k): str(v) for k, v in (params or {}).items()}
    )
    url = CZAR28_BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query

    headers = {
        "Accept": "application/json",
        "User-Agent": "ATLAS-czar28-historical-options-qualification-v1/1",
    }
    if authenticate:
        headers["Authorization"] = f"Bearer {key}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    last_error: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
                return Czar28Response(
                    http_status=int(response.status),
                    payload=_decode_json(raw),
                    headers={str(k): str(v) for k, v in response.headers.items()},
                    response_bytes=len(raw),
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                    transport_attempts=attempt,
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            response_headers = {str(k): str(v) for k, v in exc.headers.items()}
            payload = _safe_decode_json(raw)

            if exc.code == 429:
                error_code = str(payload.get("error") or "quota_exceeded")
                raise Czar28QuotaExhausted(
                    f"Czar28 quota/rate limit returned HTTP 429: "
                    f"{error_code}",
                    transport_attempts=attempt,
                    http_status=429,
                    error_code=error_code,
                ) from exc

            if exc.code == 404:
                return Czar28Response(
                    http_status=404,
                    payload=payload,
                    headers=response_headers,
                    response_bytes=len(raw),
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                    transport_attempts=attempt,
                )

            if exc.code in CZAR28_TRANSIENT_HTTP_STATUS and attempt < max_attempts:
                retry_after = _retry_after_seconds(response_headers)
                backoff = min(
                    max_retry_seconds,
                    initial_retry_seconds * (2 ** (attempt - 1)),
                )
                sleep(max(backoff, retry_after or 0.0))
                last_error = exc
                continue

            suffix = (
                f" after {attempt} transport attempts"
                if attempt > 1
                else ""
            )
            error_code = str(
                payload.get("error")
                or payload.get("message")
                or payload.get("raw_error")
                or "http_error"
            )
            raise Czar28Error(
                f"Czar28 HTTP {exc.code}{suffix}: {error_code!r}",
                transport_attempts=attempt,
                http_status=int(exc.code),
                error_code=error_code,
            ) from exc

        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < max_attempts:
                backoff = min(
                    max_retry_seconds,
                    initial_retry_seconds * (2 ** (attempt - 1)),
                )
                sleep(backoff)
                continue
            raise Czar28Error(
                f"Czar28 transport error after {attempt} attempts: {exc}",
                transport_attempts=attempt,
                error_code="transport_error",
            ) from exc

    raise Czar28Error(
        f"Czar28 request failed after {max_attempts} attempts: {last_error}",
        transport_attempts=max_attempts,
        error_code="transport_error",
    )


def get_health(
    *,
    timeout_seconds: float = 15.0,
    max_attempts: int = 3,
) -> Czar28Response:
    """Read the public Czar28 health endpoint without consuming API-key quota."""
    return get_json(
        "options/health",
        authenticate=False,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )


def health_is_ready(payload: dict[str, Any]) -> bool:
    """Return True only for an explicitly healthy, connected upstream."""
    status = str(payload.get("status") or "").strip().lower()
    upstream = payload.get("upstream")
    mdds_status = ""
    if isinstance(upstream, dict):
        mdds_status = str(upstream.get("mdds_status") or "").strip().upper()
    return status == "ok" and mdds_status == "CONNECTED"
