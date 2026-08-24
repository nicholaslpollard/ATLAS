from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from packages.brokers.webull import harden_webull_sdk_logging


WEBULL_SANDBOX_ENDPOINT = "api.sandbox.webull.com"


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _extract_quote(payload: object, ticker: str) -> dict[str, object]:
    rows: list[dict[str, object]]
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    else:
        raise RuntimeError("Webull market-data response has unexpected shape")

    row = next((item for item in rows if str(item.get("symbol") or "") == ticker), None)
    if row is None and len(rows) == 1:
        row = rows[0]
    if row is None:
        raise RuntimeError("Webull market-data response did not contain the requested ticker")

    bids = row.get("bids")
    asks = row.get("asks")
    if not isinstance(bids, list) or not bids or not isinstance(bids[0], dict):
        raise RuntimeError("Webull market-data response did not contain a best bid")
    if not isinstance(asks, list) or not asks or not isinstance(asks[0], dict):
        raise RuntimeError("Webull market-data response did not contain a best ask")

    bid = float(bids[0].get("price") or 0.0)
    ask = float(asks[0].get("price") or 0.0)
    if bid <= 0.0 or ask <= 0.0 or ask < bid:
        raise RuntimeError("Webull market-data response contained invalid bid/ask geometry")

    quote_time_ms = int(row.get("quote_time") or 0)
    if quote_time_ms <= 0:
        raise RuntimeError("Webull market-data response did not contain quote_time")
    provider_time = datetime.fromtimestamp(quote_time_ms / 1000.0, tz=UTC)
    age_seconds = max(0.0, (datetime.now(UTC) - provider_time).total_seconds())

    return {
        "symbol": ticker,
        "bid": bid,
        "ask": ask,
        "provider_timestamp_utc": provider_time.isoformat(),
        "quote_age_seconds": round(age_seconds, 3),
        "appears_fresh_under_30s": age_seconds <= 30.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Webull sandbox L1 quote entitlement probe. "
            "Performs one market-data request and no account/order mutations."
        )
    )
    parser.add_argument("--ticker", default="AAPL")
    args = parser.parse_args()
    ticker = str(args.ticker).strip()
    if not ticker:
        raise SystemExit("ticker cannot be blank")

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    key = _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY")
    secret = _first_env("WEBULL_PAPER_APP_SECRET", "WEBULL_APP_SECRET")
    if not key or not secret:
        print("ATLAS Webull market-data diagnostic")
        print("status: BLOCKED")
        print("reason: Webull paper/sandbox credentials are unavailable")
        print("provider_read_calls: 0")
        print("provider_writes: 0")
        print("broker_writes: 0")
        return 2

    harden_webull_sdk_logging()
    try:
        from webull.core.client import ApiClient
        from webull.data.data_client import DataClient
    except ImportError:
        print("ATLAS Webull market-data diagnostic")
        print("status: BLOCKED")
        print("reason: webull-openapi-python-sdk is unavailable")
        print("provider_read_calls: 0")
        print("provider_writes: 0")
        print("broker_writes: 0")
        return 2

    api_client = ApiClient(key, secret, "us")
    api_client.add_endpoint("us", WEBULL_SANDBOX_ENDPOINT)
    data_client = DataClient(api_client)

    print("ATLAS Webull market-data diagnostic")
    print("environment: SANDBOX")
    print(f"ticker: {ticker}")
    print("request: L1 best bid/ask depth=1")
    print("provider_writes: 0")
    print("broker_writes: 0")

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
        print("provider_read_calls: 1")
        return 2

    status_code = int(getattr(response, "status_code", 0))
    print(f"http_status: {status_code}")
    print("provider_read_calls: 1")
    if status_code != 200:
        print("status: BLOCKED")
        print("reason: Webull market-data endpoint did not authorize/accept the request")
        return 2

    try:
        quote = _extract_quote(response.json(), ticker)
    except Exception as exc:
        print("status: BLOCKED")
        print(f"reason: {exc}")
        return 2

    print("status: QUOTE_RECEIVED")
    print(f"bid_ask: {quote['bid']}/{quote['ask']}")
    print(f"provider_timestamp_utc: {quote['provider_timestamp_utc']}")
    print(f"quote_age_seconds: {quote['quote_age_seconds']}")
    print(f"appears_fresh_under_30s: {quote['appears_fresh_under_30s']}")
    print("note: freshness alone is diagnostic; it does not authorize Phase 18 mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
