from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_dia_gap_diagnostic_v1 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_marketdata_massive_dia_gap_diagnostic_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose the DIA missing-aggregate failure from the frozen "
            "MarketData x Massive disjoint EOD validation."
        )
    )
    parser.add_argument(
        "--authorize-massive-provider-reads",
        action="store_true",
        help=(
            "Required explicit authorization for bounded read-only Massive "
            "trade/condition diagnostics."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_massive_provider_reads:
        print(
            "BLOCKED: pass --authorize-massive-provider-reads to permit the "
            "bounded DIA gap diagnostic."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS MarketData x Massive DIA Aggregate-Gap Diagnostic V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print(
        "  frozen failed validation: "
        f"{CONTRACT['failed_validation']['run_id']} / "
        f"{CONTRACT['failed_validation']['evidence_fingerprint']}"
    )
    print(
        "  target: "
        f"{CONTRACT['target']['massive_ticker']} "
        f"{CONTRACT['target']['from_date']}..{CONTRACT['target']['to_date']}"
    )
    print("  original V1 verdict: VALIDATION_FAILED / immutable")
    print("  MarketData calls: 0 / accepted local raw evidence is reused")
    print(
        "  Massive reads: one options-trade conditions query plus one bounded "
        "trade query for each missing DIA aggregate date"
    )
    print("  frozen validation thresholds: unchanged")
    print("  historical-price/PAPER/LIVE/order authority: false")

    report = run_marketdata_massive_dia_gap_diagnostic_v1(settings)

    print("\nDIA AGGREGATE-GAP DIAGNOSTIC: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        "  MarketData EOD dates: "
        + ", ".join(report["marketdata_dates"])
    )
    print(
        "  Massive aggregate dates: "
        + ", ".join(report["massive_aggregate_dates"])
    )
    print(
        "  missing aggregate dates: "
        + ", ".join(report["missing_aggregate_dates"])
    )
    print(f"  condition metadata rows: {report['condition_metadata_count']}")
    print(
        "  condition metadata pagination truncated: "
        f"{report['conditions_pages_truncated']}"
    )
    for item in report["days"]:
        print(
            "  "
            f"{item.get('date')}: "
            f"md_last={item.get('marketdata_last')} "
            f"md_volume={item.get('marketdata_volume')} "
            f"raw_trades={item.get('raw_trade_count')} "
            f"price_eligible={item.get('price_eligible_trade_count')} "
            f"volume_eligible={item.get('volume_eligible_trade_count')} "
            f"ineligible={item.get('aggregate_ineligible_trade_count')} "
            f"unresolved={item.get('aggregate_eligibility_unresolved_trade_count')} "
            f"conditions={item.get('condition_counts')} "
            f"disposition={item.get('disposition')} "
            f"truncated={item.get('massive_trade_pages_truncated')} "
            f"error={item.get('error')}"
        )
    print(f"  disposition counts: {report['disposition_counts']}")
    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: diagnostic only; V1 remains failed and no threshold, "
        "historical-price, bid/ask, simulator, strategy, PAPER or LIVE authority changes"
    )
    return 0 if report["status"] == "DIAGNOSTIC_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
