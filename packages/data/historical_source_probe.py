from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


HISTORICAL_SOURCE_AUDIT_CONTRACT_VERSION = (
    "historical-source-audit-v1-alpaca-marketdata-stooq-csv-access"
)
ALPACA_MARKET_DATA_BASE_URL = "https://data.alpaca.markets"
STOOQ_DAILY_CSV_URL = "https://stooq.com/q/d/l/"
HTTP_TIMEOUT_SECONDS = 30.0
USER_AGENT = "ATLAS-historical-source-audit/1.0"

ALPACA_CREDENTIAL_PROFILES = {
    "paper": ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET"),
    "live": ("ALPACA_LIVE_API_KEY", "ALPACA_LIVE_API_SECRET"),
}


@dataclass(frozen=True, slots=True)
class HTTPProbeResult:
    status: str
    http_status: int | None
    message: str | None
    response_headers: dict[str, str]
    payload: Any | None


@dataclass(frozen=True, slots=True)
class HistoricalSourceAuditReport:
    contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    alpaca: dict[str, object]
    stooq: dict[str, object]
    report_path: str


def _safe_headers(headers: Any) -> dict[str, str]:
    wanted = {
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "content-type",
    }
    output: dict[str, str] = {}
    if headers is None:
        return output
    for key, value in headers.items():
        normalized = str(key).lower()
        if normalized in wanted:
            output[normalized] = str(value)
    return output


def _http_get(url: str, *, headers: dict[str, str] | None = None) -> HTTPProbeResult:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,*/*"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers, method="GET")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            text = raw.decode("utf-8", errors="replace")
            payload: Any
            if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = text
            else:
                payload = text
            return HTTPProbeResult(
                status="OK",
                http_status=int(getattr(response, "status", 200)),
                message=None,
                response_headers=_safe_headers(response.headers),
                payload=payload,
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = body[:1000]
        if exc.code == 401:
            status = "AUTH_ERROR"
        elif exc.code == 403:
            status = "FORBIDDEN"
        elif exc.code == 429:
            status = "RATE_LIMITED"
        else:
            status = "HTTP_ERROR"
        return HTTPProbeResult(
            status=status,
            http_status=int(exc.code),
            message=str(exc.reason),
            response_headers=_safe_headers(exc.headers),
            payload=payload,
        )
    except (URLError, TimeoutError, OSError) as exc:
        return HTTPProbeResult(
            status="NETWORK_ERROR",
            http_status=None,
            message=str(exc),
            response_headers={},
            payload=None,
        )


def _alpaca_headers(key: str, secret: str) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }


def alpaca_bar_url(
    symbol: str,
    *,
    start: str,
    end: str,
    feed: str,
    adjustment: str = "raw",
    asof: str = "-",
) -> str:
    params = urlencode(
        {
            "timeframe": "1Day",
            "start": start,
            "end": end,
            "limit": 10000,
            "adjustment": adjustment,
            "asof": asof,
            "feed": feed,
            "sort": "asc",
        }
    )
    return f"{ALPACA_MARKET_DATA_BASE_URL}/v2/stocks/{symbol}/bars?{params}"


def alpaca_corporate_actions_url(*, symbols: str, start: str, end: str) -> str:
    return (
        f"{ALPACA_MARKET_DATA_BASE_URL}/v1/corporate-actions?"
        + urlencode({"symbols": symbols, "start": start, "end": end})
    )


def stooq_daily_url(symbol: str, *, start: str, end: str) -> str:
    return STOOQ_DAILY_CSV_URL + "?" + urlencode(
        {
            "s": symbol.lower(),
            "d1": start.replace("-", ""),
            "d2": end.replace("-", ""),
            "i": "d",
        }
    )


def _summarize_alpaca_bars(result: HTTPProbeResult) -> dict[str, object]:
    summary: dict[str, object] = {
        "status": result.status,
        "http_status": result.http_status,
        "message": result.message,
        "response_headers": result.response_headers,
        "bar_count": 0,
        "first_timestamp": None,
        "last_timestamp": None,
    }
    payload = result.payload
    if result.status != "OK" or not isinstance(payload, dict):
        if isinstance(payload, dict):
            summary["provider_message"] = payload.get("message")
        return summary
    bars = payload.get("bars")
    if not isinstance(bars, list):
        return summary
    summary["bar_count"] = len(bars)
    if bars:
        first = bars[0] if isinstance(bars[0], dict) else {}
        last = bars[-1] if isinstance(bars[-1], dict) else {}
        summary["first_timestamp"] = first.get("t")
        summary["last_timestamp"] = last.get("t")
        summary["first_bar"] = {key: first.get(key) for key in ("t", "o", "h", "l", "c", "v")}
        summary["last_bar"] = {key: last.get(key) for key in ("t", "o", "h", "l", "c", "v")}
    summary["next_page_token_present"] = bool(payload.get("next_page_token"))
    return summary


def parse_stooq_csv(text: str) -> list[dict[str, str]]:
    stripped = text.strip()
    if not stripped:
        return []
    reader = csv.DictReader(io.StringIO(stripped))
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        return []
    return [dict(row) for row in reader]


def _summarize_stooq(result: HTTPProbeResult) -> dict[str, object]:
    summary: dict[str, object] = {
        "status": result.status,
        "http_status": result.http_status,
        "message": result.message,
        "row_count": 0,
        "first_date": None,
        "last_date": None,
    }
    if result.status != "OK" or not isinstance(result.payload, str):
        return summary
    rows = parse_stooq_csv(result.payload)
    summary["row_count"] = len(rows)
    if rows:
        summary["first_date"] = rows[0].get("Date")
        summary["last_date"] = rows[-1].get("Date")
        summary["first_row"] = rows[0]
        summary["last_row"] = rows[-1]
    else:
        summary["response_preview"] = result.payload[:300]
    return summary


class HistoricalSourceAccessProbe:
    """Read-only access probe for possible pre-Massive historical data sources.

    The probe never writes canonical/provider history and never logs Alpaca credentials.
    It only records access/coverage evidence needed before ATLAS decides whether either
    provider is suitable for a separate historical source audit.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        load_dotenv(settings.project_root / ".env", override=False)

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "historical_source_audit" / "access_probe.json"

    def _alpaca_profile(self, profile: str, key_env: str, secret_env: str) -> dict[str, object]:
        key = os.getenv(key_env, "").strip()
        secret = os.getenv(secret_env, "").strip()
        output: dict[str, object] = {
            "configured": bool(key and secret),
            "key_env": key_env,
            "secret_env": secret_env,
            "credentials_echoed": False,
        }
        if not key or not secret:
            output["status"] = "NOT_CONFIGURED"
            return output

        headers = _alpaca_headers(key, secret)
        tests: dict[str, object] = {}
        for feed in ("sip", "iex"):
            result = _http_get(
                alpaca_bar_url(
                    "AAPL",
                    start="2016-01-04",
                    end="2016-01-15",
                    feed=feed,
                ),
                headers=headers,
            )
            tests[f"aapl_2016_{feed}_raw_literal"] = _summarize_alpaca_bars(result)

        tests["twtr_2021_iex_raw_literal"] = _summarize_alpaca_bars(
            _http_get(
                alpaca_bar_url(
                    "TWTR",
                    start="2021-01-04",
                    end="2021-01-15",
                    feed="iex",
                ),
                headers=headers,
            )
        )
        tests["meta_rename_literal_iex"] = _summarize_alpaca_bars(
            _http_get(
                alpaca_bar_url(
                    "FB",
                    start="2022-06-01",
                    end="2022-06-08",
                    feed="iex",
                ),
                headers=headers,
            )
        )

        corporate = _http_get(
            alpaca_corporate_actions_url(
                symbols="AAPL,NVDA,TSLA",
                start="2019-01-01",
                end="2024-12-31",
            ),
            headers=headers,
        )
        corporate_summary: dict[str, object] = {
            "status": corporate.status,
            "http_status": corporate.http_status,
            "message": corporate.message,
            "response_headers": corporate.response_headers,
        }
        if isinstance(corporate.payload, dict):
            corporate_summary["top_level_keys"] = sorted(corporate.payload.keys())
            corporate_summary["provider_message"] = corporate.payload.get("message")
            corporate_summary["payload_preview"] = json.loads(
                json.dumps(corporate.payload, default=str)[:5000]
            ) if len(json.dumps(corporate.payload, default=str)) <= 5000 else "PAYLOAD_TOO_LARGE"
        output["tests"] = tests
        output["corporate_actions"] = corporate_summary
        output["status"] = "PROBED"
        return output

    def _stooq(self) -> dict[str, object]:
        tests = {
            "aapl_2010": _summarize_stooq(
                _http_get(
                    stooq_daily_url(
                        "aapl.us",
                        start="2010-01-04",
                        end="2010-01-15",
                    )
                )
            ),
            "nvda_2024_split_window": _summarize_stooq(
                _http_get(
                    stooq_daily_url(
                        "nvda.us",
                        start="2024-06-06",
                        end="2024-06-12",
                    )
                )
            ),
            "spy_2006": _summarize_stooq(
                _http_get(
                    stooq_daily_url(
                        "spy.us",
                        start="2006-01-03",
                        end="2006-01-13",
                    )
                )
            ),
        }
        return {
            "endpoint": STOOQ_DAILY_CSV_URL,
            "tests": tests,
            "status": "PROBED",
        }

    def run(self) -> HistoricalSourceAuditReport:
        alpaca = {
            profile: self._alpaca_profile(profile, key_env, secret_env)
            for profile, (key_env, secret_env) in ALPACA_CREDENTIAL_PROFILES.items()
        }
        report = HistoricalSourceAuditReport(
            contract_version=HISTORICAL_SOURCE_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            alpaca=alpaca,
            stooq=self._stooq(),
            report_path=str(self.report_path()),
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
