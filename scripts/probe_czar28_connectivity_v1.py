from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.czar28_connectivity_preflight import (
    CZAR28_CONNECTIVITY_PREFLIGHT_V1_FINGERPRINT,
    run_czar28_connectivity_preflight_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a four-step Czar28 connectivity/history preflight before the "
            "full 1,000-call historical-options qualification."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for read-only Czar28 API calls.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit read-only "
            "Czar28 connectivity/history probes."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS Czar28 Connectivity + Historical Depth Preflight V1")
    print(
        "  contract fingerprint: "
        f"{CZAR28_CONNECTIVITY_PREFLIGHT_V1_FINGERPRINT}"
    )
    print("  probe ladder: health -> current SPY -> recent expired SPY -> 2016 SPY")
    print("  max transport attempts per probe: 3")
    print("  provider writes: 0")
    print("  broker/order/PAPER/LIVE authority: false")

    report = run_czar28_connectivity_preflight_v1(settings)

    print("\nCZAR28 PREFLIGHT: " + str(report["classification"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        "  physical HTTP attempts: "
        f"{int(report['total_physical_http_attempts']):,}"
    )
    print("  results:")
    for result in report["results"]:
        print(
            "    "
            f"{result['name']}: status={result['status']} "
            f"http={result['http_status']} rows={result['row_count']} "
            f"attempts={result['transport_attempts']} "
            f"health={result['health_status']} "
            f"upstream={result['upstream_status']} "
            f"remaining={result['provider_remaining']} "
            f"error={result['error']}"
        )
    print(f"  report: {report['report_path']}")

    if report["classification"] == "PREFLIGHT_PASS":
        print(
            "  next: safe to proceed to the frozen 1,000-call Czar28 "
            "historical-option qualification"
        )
        return 0

    print(
        "  next: do NOT start the 1,000-call qualification; diagnose this "
        "preflight classification first"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
