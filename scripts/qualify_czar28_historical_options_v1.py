from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.providers.czar28 import Czar28Error, get_health, health_is_ready
from packages.data.czar28_historical_option_qualification import (
    CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT,
    MAX_FREE_REQUESTS,
    MAX_QUALIFICATION_RPM,
    run_czar28_historical_option_qualification_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Czar28/PublicOptions historical-option source qualification. "
            "Uses the free-tier quota deliberately but creates no historical-data, "
            "strategy, PAPER, or LIVE authority."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for read-only Czar28 API calls.",
    )
    parser.add_argument(
        "--consume-free-quota",
        action="store_true",
        help=(
            "Required second gate acknowledging that the run may consume up to the "
            "entire free monthly request quota."
        ),
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=MAX_FREE_REQUESTS,
        help=f"Maximum provider calls this run, 1..{MAX_FREE_REQUESTS}.",
    )
    parser.add_argument(
        "--requests-per-minute",
        type=int,
        default=MAX_QUALIFICATION_RPM,
        help=(
            f"Local pacing ceiling, 1..{MAX_QUALIFICATION_RPM}. "
            "The provider documents 60/min for Free."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit read-only "
            "Czar28 historical-option calls."
        )
        return 2
    if not args.consume_free_quota:
        print(
            "BLOCKED: pass --consume-free-quota to acknowledge intentional "
            "consumption of the Czar28 free monthly request allowance."
        )
        return 2
    if not 1 <= args.max_requests <= MAX_FREE_REQUESTS:
        print(f"BLOCKED: --max-requests must be within 1..{MAX_FREE_REQUESTS}.")
        return 2
    if not 1 <= args.requests_per_minute <= MAX_QUALIFICATION_RPM:
        print(
            f"BLOCKED: --requests-per-minute must be within "
            f"1..{MAX_QUALIFICATION_RPM}."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")

    print("ATLAS Czar28 Historical Option Source Qualification V1")
    print("  mandatory public health gate: checking...")
    try:
        health = get_health()
    except Czar28Error as exc:
        print(
            "BLOCKED: Czar28 public health check failed before any "
            f"quota-consuming request: {type(exc).__name__}: {exc}"
        )
        return 4

    upstream = health.payload.get("upstream")
    upstream_status = None
    upstream_message = None
    if isinstance(upstream, dict):
        upstream_status = upstream.get("mdds_status")
        upstream_message = upstream.get("message")
    print(
        "  health: "
        f"status={health.payload.get('status')} "
        f"upstream={upstream_status} "
        f"message={upstream_message}"
    )
    if not health_is_ready(health.payload):
        print(
            "BLOCKED: Czar28 is not explicitly healthy/CONNECTED. "
            "No quota-consuming qualification calls were sent."
        )
        return 4

    print("  mandatory public health gate: checking...")
    try:
        health = get_health()
    except Czar28Error as exc:
        print(
            "BLOCKED: Czar28 public health check failed before any "
            f"quota-consuming request: {type(exc).__name__}: {exc}"
        )
        return 4

    upstream = health.payload.get("upstream")
    upstream_status = None
    upstream_message = None
    if isinstance(upstream, dict):
        upstream_status = upstream.get("mdds_status")
        upstream_message = upstream.get("message")
    print(
        "  health: "
        f"status={health.payload.get('status')} "
        f"upstream={upstream_status} "
        f"message={upstream_message}"
    )
    if not health_is_ready(health.payload):
        print(
            "BLOCKED: Czar28 is not explicitly healthy/CONNECTED. "
            "No quota-consuming qualification calls were sent."
        )
        return 4

    print(
        "  contract fingerprint: "
        f"{CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT}"
    )
    print("  credential env: CZAR_API_KEY")
    print("  stock-aligned anchor span: 2016..2026")
    print("  anchor roots: 30")
    print(f"  maximum provider calls this run: {args.max_requests:,}")
    print(f"  local pacing ceiling: {args.requests_per_minute}/minute")
    print("  provider writes: 0")
    print("  broker reads/writes: 0/0")
    print("  order authority: false")
    print("  PAPER/LIVE authority: false")
    print("  strategy outcome access: false")
    print("  raw responses + hash-bound receipts: enabled")
    print("  restart/reuse of completed probes: enabled")

    report = run_czar28_historical_option_qualification_v1(
        settings,
        max_requests=args.max_requests,
        requests_per_minute=args.requests_per_minute,
    )

    print("\nCZAR28 HISTORICAL OPTION QUALIFICATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        "  logical provider calls this run: "
        f"{int(report['provider_request_attempts_this_run']):,}"
    )
    print(
        "  physical HTTP attempts this run: "
        f"{int(report.get('provider_transport_attempts_this_run') or 0):,}"
    )
    print(
        "  observed quota: "
        f"limit={report['provider_limit_observed']} "
        f"remaining={report['provider_remaining_observed']} "
        f"reset={report['provider_reset_observed']}"
    )
    print(
        "  observed minute controls: "
        f"limit={report['provider_minute_limit_observed']} "
        f"burst={report['provider_burst_observed']}"
    )
    print("  probe kinds: " + json.dumps(report["kind_counts"], sort_keys=True))
    print(
        "  non-empty probe kinds: "
        + json.dumps(report["nonempty_by_kind"], sort_keys=True)
    )
    print(
        "  full 2016..2026 chain + EOD presence: "
        f"{report['full_2016_through_2026_chain_and_eod_presence']}"
    )
    print(
        "  all four endpoint classes non-empty: "
        f"{report['all_four_endpoint_classes_nonempty']}"
    )
    print(
        "  chain repeat stability: "
        + json.dumps(report["chain_repeat_stability"], sort_keys=True)
    )
    print(
        "  EOD repeat stability: "
        + json.dumps(report["eod_repeat_stability"], sort_keys=True)
    )
    print("  per-year evidence:")
    for year, stats in dict(report["year_stats"]).items():
        print(
            f"    {year}: "
            f"chain={stats.get('chain_nonempty', 0)}/"
            f"{stats.get('chain_probes', 0)} non-empty, "
            f"eod={stats.get('eod_nonempty', 0)}/"
            f"{stats.get('eod_probes', 0)} non-empty"
        )
    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: diagnostic only; cross-provider price validation remains "
        "required before Czar28 can become a historical market-data authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
