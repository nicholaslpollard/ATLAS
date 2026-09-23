from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_dia_aggregate_surface_v1 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_marketdata_massive_dia_aggregate_surface_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Massive daily and one-minute aggregate availability across "
            "the frozen DIA validation window using Options Basic-accessible data."
        )
    )
    parser.add_argument(
        "--authorize-massive-provider-reads",
        action="store_true",
        help="Required explicit authorization for nine bounded read-only Massive calls.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_massive_provider_reads:
        print(
            "BLOCKED: pass --authorize-massive-provider-reads to permit the "
            "bounded DIA aggregate-surface diagnostic."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS MarketData x Massive DIA Aggregate-Surface Diagnostic V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    trigger = CONTRACT["triggering_diagnostic"]
    print(
        "  triggering incomplete diagnostic: "
        f"{trigger['run_id']} / {trigger['evidence_fingerprint']}"
    )
    print(
        "  target: "
        f"{CONTRACT['target']['massive_ticker']} "
        f"{CONTRACT['target']['from_date']}..{CONTRACT['target']['to_date']}"
    )
    print("  original disjoint V1 verdict: VALIDATION_FAILED / immutable")
    print("  raw-trade V1 diagnostic: DIAGNOSTIC_INCOMPLETE / HTTP 403")
    print("  MarketData calls: 0 / accepted local raw evidence is reused")
    print("  Massive reads: 9 / one 1-minute aggregate query per DIA EOD date")
    print("  provider plan target: Options Basic-accessible aggregate surface")
    print("  historical-price/PAPER/LIVE/order authority: false")

    report = run_marketdata_massive_dia_aggregate_surface_v1(settings)

    print("\nDIA AGGREGATE-SURFACE DIAGNOSTIC: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print("  Massive daily dates: " + ", ".join(report["massive_daily_dates"]))
    print("  missing daily dates: " + ", ".join(report["missing_daily_dates"]))
    for item in report["records"]:
        print(
            "  "
            f"{item.get('date')}: "
            f"daily_present={item.get('daily_present')} "
            f"md_volume={item.get('marketdata_volume')} "
            f"minute_rows={item.get('minute_aggregate_rows')} "
            f"minute_volume={item.get('minute_aggregate_volume_sum')} "
            f"disposition={item.get('disposition')} "
            f"error={item.get('error')}"
        )
    print(f"  disposition counts: {report['disposition_counts']}")
    print(f"  aggregate surfaces consistent: {report['surface_consistent']}")
    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: diagnostic only; raw-trade presence remains unresolved, "
        "V1 remains failed, and no historical-price/simulator/PAPER/LIVE authority changes"
    )
    return 0 if report["status"] != "DIAGNOSTIC_INCOMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
