from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_five_year_options_qualification import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_marketdata_five_year_options_qualification_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MarketData.app five-year historical options source qualification."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for read-only MarketData.app calls.",
    )
    parser.add_argument(
        "--starter-trial",
        action="store_true",
        help=(
            "Use the Starter Trial capability probe: deep AAPL plus recent "
            "multi-ticker anchors inside the trial's one-year general limit."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit read-only "
            "MarketData.app historical-option calls."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")

    print("ATLAS MarketData.app Five-Year Historical Options Qualification V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print("  credential env: MARKETDATA_TOKEN")
    if args.starter_trial:
        print("  target plan: Starter Trial ($0 / 30 days)")
        print("  target historical window: 1 year general / deep AAPL exception")
        print(f"  anchor probes: {len(CONTRACT['starter_trial_anchors'])}")
    else:
        print("  target plan: Starter ($30 month-to-month)")
        print("  target historical window: rolling 5 years")
        print(f"  anchor probes: {len(CONTRACT['anchors'])}")
    print("  chain shape: historical EOD / dte=30 / strikeLimit=8")
    print("  quote series: 10 calendar days for selected contract")
    print("  expected historical fields: bid/ask/mid/last/volume/OI/underlyingPrice")
    print("  historical Greeks: expected null")
    print("  raw responses + SHA-256 receipts: enabled")
    print("  provider writes: 0")
    print("  PAPER/LIVE/order authority: false")

    report = run_marketdata_five_year_options_qualification_v1(
        settings,
        starter_trial=args.starter_trial,
    )

    print("\nMARKETDATA OPTIONS QUALIFICATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(f"  oldest 2021-10-01 anchor proven: {report['oldest_anchor_proven']}")
    print(
        "  broad five-year entitlement proven: "
        f"{report['broad_five_year_entitlement_proven']}"
    )
    print(f"  all anchor chains non-empty: {report['all_anchor_chains_nonempty']}")
    print(f"  all quote series non-empty: {report['all_quote_series_nonempty']}")
    print(
        "  open interest present across anchors: "
        f"{report['open_interest_present_across_anchors']}"
    )
    print(
        "  usable bid/ask across anchors: "
        f"{report['usable_bid_ask_across_anchors']}"
    )
    print(
        "  required schema present across anchors: "
        f"{report['required_schema_present_across_anchors']}"
    )
    print(
        "  historical Greeks present and null across anchors: "
        f"{report['historical_greeks_present_and_null_across_anchors']}"
    )
    print(
        "  observed API credits consumed: "
        f"{report['observed_api_credits_consumed']}"
    )
    print(
        "  last observed API credits remaining: "
        f"{report['last_observed_api_credits_remaining']}"
    )
    for item in report["anchors"]:
        print(
            "  "
            f"{item.get('date')} {item.get('root')}: "
            f"chain_rows={item.get('chain_rows')} "
            f"chain_oi={item.get('chain_open_interest_nonnull')} "
            f"chain_bidask={item.get('chain_usable_bid_ask_rows')} "
            f"contract={item.get('selected_option_symbol')} "
            f"quote_rows={item.get('quote_rows')} "
            f"quote_oi={item.get('quote_open_interest_nonnull')} "
            f"quote_bidask={item.get('quote_usable_bid_ask_rows')} "
            f"error={item.get('error')}"
        )
    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: diagnostic challenger only; cross-provider validation and "
        "simulator integration remain separate gates"
    )
    qualified_statuses = {
        "QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY",
        "QUALIFIED_FOR_FIVE_YEAR_EOD_ECONOMICS_CHALLENGER",
    }
    return 0 if report["status"] in qualified_statuses else 3


if __name__ == "__main__":
    raise SystemExit(main())
