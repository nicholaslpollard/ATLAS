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
from packages.core.settings import load_settings
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteBundleError,
    build_current_webull_stock_quote_bundle_v1,
    parse_current_webull_stock_quote_v1,
    write_current_webull_stock_quote_bundle_v1,
)


WEBULL_SANDBOX_ENDPOINT = "api.sandbox.webull.com"


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _symbols(value: str) -> tuple[str, ...]:
    items = tuple(
        sorted(
            item.strip()
            for item in str(value).split(",")
            if item.strip()
        )
    )
    if not items:
        raise argparse.ArgumentTypeError(
            "at least one comma-separated ticker is required"
        )
    if len(items) != len(set(items)):
        raise argparse.ArgumentTypeError(
            "ticker list cannot contain duplicates"
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a complete sanitized Webull sandbox L1 quote bundle "
            "for exact US stock symbols. Performs one read per symbol and "
            "no provider/broker mutation."
        )
    )
    parser.add_argument(
        "--tickers",
        required=True,
        type=_symbols,
        help="Comma-separated exact provider-native stock tickers.",
    )
    args = parser.parse_args()
    symbols: tuple[str, ...] = args.tickers

    settings = load_settings(PROJECT_ROOT)
    key = _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY")
    secret = _first_env(
        "WEBULL_PAPER_APP_SECRET",
        "WEBULL_APP_SECRET",
    )

    print("ATLAS current Webull stock L1 quote bundle capture")
    print("environment: SANDBOX")
    print(f"symbols: {','.join(symbols)}")
    print(f"provider_read_calls_planned: {len(symbols)}")
    print("provider_writes: 0")
    print("broker_reads: 0")
    print("broker_writes: 0")
    print("partial_bundle_persistence: disabled")

    from packages.execution.current_webull_quote_bundle import (
        current_webull_stock_quote_bundle_path,
    )
    current_path = current_webull_stock_quote_bundle_path(settings)
    try:
        current_path.unlink(missing_ok=True)
    except OSError as exc:
        print("status: BLOCKED")
        print(
            "reason: prior current quote bundle could not be invalidated: "
            f"{type(exc).__name__}"
        )
        return 2
    print("prior_current_bundle_invalidated: True")

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

    quotes = []
    for symbol in symbols:
        try:
            response = data_client.market_data.get_quotes(
                symbol=symbol,
                category="US_STOCK",
                depth=1,
                overnight_required=False,
            )
        except Exception as exc:
            print("status: BLOCKED")
            print(
                "reason: Webull market-data request raised "
                f"{type(exc).__name__} for {symbol}"
            )
            return 2
        status_code = int(getattr(response, "status_code", 0))
        if status_code != 200:
            print("status: BLOCKED")
            print(
                f"reason: Webull market-data request for {symbol} "
                f"returned HTTP {status_code}"
            )
            return 2
        received_at = datetime.now(UTC)
        try:
            quote = parse_current_webull_stock_quote_v1(
                settings=settings,
                payload=response.json(),
                symbol=symbol,
                received_at_utc=received_at,
            )
        except (
            CurrentWebullStockQuoteBundleError,
            ValueError,
        ) as exc:
            print("status: BLOCKED")
            print(f"reason: {exc}")
            return 2
        quotes.append(quote)

    captured_at = datetime.now(UTC)
    try:
        bundle = build_current_webull_stock_quote_bundle_v1(
            requested_symbols=symbols,
            quotes=quotes,
            captured_at_utc=captured_at,
        )
        path = write_current_webull_stock_quote_bundle_v1(
            settings,
            bundle,
        )
    except CurrentWebullStockQuoteBundleError as exc:
        print("status: BLOCKED")
        print(f"reason: {exc}")
        return 2

    print("status: CAPTURED")
    print(f"quote_count: {len(bundle.quotes)}")
    print(f"provider_read_calls: {bundle.provider_read_calls}")
    print(f"bundle_fingerprint: {bundle.bundle_fingerprint}")
    print(f"captured_at_utc: {bundle.captured_at_utc.isoformat()}")
    print(f"local_evidence_file: {path}")
    print("note: quote bundle creates no order or trading authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
