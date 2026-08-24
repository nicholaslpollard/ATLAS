from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.brokers.webull import harden_webull_sdk_logging
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.phase18_webull_quote import (
    Phase18WebullQuoteEvidence,
    write_phase18_webull_quote_evidence,
)


WEBULL_SANDBOX_ENDPOINT = "api.sandbox.webull.com"


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _extract_quote(payload: object, ticker: str) -> tuple[float, int, float, int, datetime]:
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    else:
        raise RuntimeError("Webull market-data response has unexpected shape")

    row = next((item for item in rows if str(item.get("symbol") or "") == ticker), None)
    if row is None:
        raise RuntimeError("Webull market-data response did not contain the exact requested ticker")

    bids = row.get("bids")
    asks = row.get("asks")
    if not isinstance(bids, list) or not bids or not isinstance(bids[0], dict):
        raise RuntimeError("Webull market-data response did not contain a best bid")
    if not isinstance(asks, list) or not asks or not isinstance(asks[0], dict):
        raise RuntimeError("Webull market-data response did not contain a best ask")

    bid = float(bids[0].get("price") or 0.0)
    ask = float(asks[0].get("price") or 0.0)
    bid_size = int(float(bids[0].get("size") or 0))
    ask_size = int(float(asks[0].get("size") or 0))
    if bid <= 0.0 or ask <= 0.0 or ask < bid:
        raise RuntimeError("Webull market-data response contained invalid bid/ask geometry")

    quote_time_ms = int(row.get("quote_time") or 0)
    if quote_time_ms <= 0:
        raise RuntimeError("Webull market-data response did not contain quote_time")
    provider_time = datetime.fromtimestamp(quote_time_ms / 1000.0, tz=UTC)
    return bid, bid_size, ask, ask_size, provider_time


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture one sanitized read-only Webull sandbox L1 quote for Phase 18. "
            "Performs exactly one market-data read and no broker/provider mutation."
        )
    )
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    ticker = str(args.ticker).strip()
    if not ticker:
        raise SystemExit("ticker cannot be blank")

    settings = load_settings(PROJECT_ROOT)
    key = _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY")
    secret = _first_env("WEBULL_PAPER_APP_SECRET", "WEBULL_APP_SECRET")

    print("ATLAS Phase 18 Webull quote capture")
    print("environment: SANDBOX")
    print(f"ticker: {ticker}")
    print("request: L1 best bid/ask depth=1")
    print("provider_read_calls: 1")
    print("provider_writes: 0")
    print("broker_writes: 0")

    if not key or not secret:
        print("status: BLOCKED")
        print("reason: Webull paper/sandbox credentials are unavailable")
        return 2

    harden_webull_sdk_logging()
    try:
        from webull.core.client import ApiClient
        from webull.data.data_client import DataClient
    except ImportError:
        print("status: BLOCKED")
        print("reason: webull-openapi-python-sdk is unavailable")
        return 2

    api_client = ApiClient(key, secret, "us")
    api_client.add_endpoint("us", WEBULL_SANDBOX_ENDPOINT)
    data_client = DataClient(api_client)

    try:
        response = data_client.market_data.get_quotes(
            symbol=ticker,
            category="US_STOCK",
            depth=1,
            overnight_required=False,
        )
    except Exception as exc:
        print("status: BLOCKED")
        print(f"reason: Webull market-data request raised {type(exc).__name__}")
        return 2

    status_code = int(getattr(response, "status_code", 0))
    print(f"http_status: {status_code}")
    if status_code != 200:
        print("status: BLOCKED")
        print("reason: Webull market-data endpoint did not authorize/accept the request")
        return 2

    received_at = datetime.now(UTC)
    try:
        bid, bid_size, ask, ask_size, provider_time = _extract_quote(response.json(), ticker)
    except Exception as exc:
        print("status: BLOCKED")
        print(f"reason: {exc}")
        return 2

    age_seconds = (received_at - provider_time).total_seconds()
    if age_seconds < -5.0:
        print("status: BLOCKED")
        print("reason: provider timestamp is ahead of the local clock")
        return 2
    if age_seconds > PHASE15_MAX_QUOTE_AGE_SECONDS:
        print("status: BLOCKED")
        print(
            f"reason: quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap"
        )
        print(f"quote_age_seconds: {round(age_seconds, 3)}")
        return 2

    calendar = get_market_calendar(settings.data.calendar.exchange)
    segment = calendar.classify(provider_time)
    evidence = Phase18WebullQuoteEvidence(
        symbol=ticker,
        provider_timestamp_utc=provider_time,
        received_at_utc=received_at,
        session_date=provider_time.astimezone(calendar.market_tz).date(),
        session_segment=segment,
        bid_price=bid,
        bid_size=bid_size,
        ask_price=ask,
        ask_size=ask_size,
    )
    path = write_phase18_webull_quote_evidence(settings, evidence)

    print("status: CAPTURED")
    print(f"bid_ask: {bid}/{ask}")
    print(f"provider_timestamp_utc: {provider_time.isoformat()}")
    print(f"quote_age_seconds: {round(age_seconds, 3)}")
    print(f"session_segment: {segment.value}")
    print(f"fresh_under_{PHASE15_MAX_QUOTE_AGE_SECONDS}s: True")
    print(f"local_evidence_file: {path}")
    print("note: local quote evidence creates no trading authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
