from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


CZAR28_BASE_URL = "https://api.czar28.com/v1"
CZAR28_CREDENTIAL_ENV = "CZAR_API_KEY"


class Czar28Error(RuntimeError):
    pass


class Czar28QuotaExhausted(Czar28Error):
    pass


@dataclass(frozen=True, slots=True)
class Czar28Response:
    http_status: int
    payload: dict[str, Any]
    headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float


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


def get_json(
    path: str,
    *,
    params: dict[str, object] | None = None,
    idempotency_key: str | None = None,
    timeout_seconds: float = 30.0,
    api_key: str | None = None,
) -> Czar28Response:
    key = (api_key or _resolve_api_key()).strip()
    query = urllib.parse.urlencode(
        {str(k): str(v) for k, v in (params or {}).items()}
    )
    url = CZAR28_BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "ATLAS-czar28-historical-options-qualification-v1/1",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            return Czar28Response(
                http_status=int(response.status),
                payload=_decode_json(raw),
                headers={str(k): str(v) for k, v in response.headers.items()},
                response_bytes=len(raw),
                elapsed_seconds=max(0.0, time.perf_counter() - started),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        response_headers = {str(k): str(v) for k, v in exc.headers.items()}
        payload = _decode_json(raw) if raw else {}
        if exc.code == 429:
            raise Czar28QuotaExhausted(
                f"Czar28 quota/rate limit returned HTTP 429: "
                f"{payload.get('error') or payload.get('message') or 'quota_exceeded'}"
            ) from exc
        if exc.code == 404:
            return Czar28Response(
                http_status=404,
                payload=payload,
                headers=response_headers,
                response_bytes=len(raw),
                elapsed_seconds=max(0.0, time.perf_counter() - started),
            )
        raise Czar28Error(
            f"Czar28 HTTP {exc.code}: "
            f"{payload.get('error') or payload.get('message') or raw[:200]!r}"
        ) from exc
    except urllib.error.URLError as exc:
        raise Czar28Error(f"Czar28 transport error: {exc}") from exc
