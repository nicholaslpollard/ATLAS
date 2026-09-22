from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.tradier_source_qualification import (
    TRADIER_SOURCE_QUALIFICATION_CONTRACT_FINGERPRINT,
    run_tradier_rest_source_qualification,
)


def _batch_sizes(value: str) -> tuple[int, ...]:
    sizes = tuple(
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    )
    if not sizes or any(item < 1 for item in sizes):
        raise argparse.ArgumentTypeError(
            "batch sizes must be a comma-separated list of positive integers"
        )
    return sizes


def _symbols(value: str) -> tuple[str, ...]:
    symbols = tuple(
        dict.fromkeys(
            item.strip()
            for item in value.split(",")
            if item.strip()
        )
    )
    if not symbols:
        raise argparse.ArgumentTypeError("symbols must not be empty")
    return symbols


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only staged Tradier production REST market-data source qualification. "
            "Creates no provider-policy or trading authority."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for the Tradier market-data REST probes.",
    )
    parser.add_argument(
        "--batch-sizes",
        type=_batch_sizes,
        default=None,
        help="Optional comma-separated staged sizes; default comes from config/tradier.yaml.",
    )
    parser.add_argument(
        "--symbols",
        type=_symbols,
        default=None,
        help=(
            "Optional explicit comma-separated symbols. If omitted, use the latest "
            "local Phase 7 discovery-eligible universe."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit read-only "
            "Tradier production market-data calls."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")

    print("ATLAS Tradier Production Market-Data Source Qualification V1")
    print(
        "  contract fingerprint: "
        f"{TRADIER_SOURCE_QUALIFICATION_CONTRACT_FINGERPRINT}"
    )
    print("  environment: production")
    print("  endpoint class: /v1/markets/quotes")
    print("  request method: POST")
    print("  provider writes: 0")
    print("  broker reads: 0")
    print("  broker writes: 0")
    print("  order authority: false")
    print("  PAPER/LIVE authority: false")
    print("  provider-policy authority: false")
    print("  streaming qualification: deferred to separate gate")

    report = run_tradier_rest_source_qualification(
        settings,
        batch_sizes=args.batch_sizes,
        symbols=args.symbols,
    )

    print("\nTRADIER REST SOURCE QUALIFICATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    source = dict(report["source"])
    print(f"  symbol source: {source['type']}")
    if "as_of_date" in source:
        print(f"  universe as-of: {source['as_of_date']}")
    print(f"  available source symbols: {int(source['symbol_count']):,}")
    print(f"  requested stages: {report['requested_batch_sizes']}")

    for stage in report["stages"]:
        stage = dict(stage)
        if stage["status"] == "FAIL":
            print(
                "  stage "
                f"{stage['requested_size']}: FAIL / "
                f"{stage['error_type']}: {stage['error']}"
            )
            continue
        print(
            "  stage "
            f"{stage['requested_size']}: {stage['status']} / "
            f"requested={stage['actual_requested_symbols']:,} "
            f"returned={stage['returned_unique_symbols']:,} "
            f"coverage={float(stage['coverage_fraction']):.3%} "
            f"provider_latency={float(stage['provider_elapsed_seconds']):.3f}s "
            f"bytes={int(stage['response_bytes']):,}"
        )
        rate = dict(stage["rate_limit"])
        print(
            "    rate limit: "
            f"allowed={rate.get('allowed')} "
            f"used={rate.get('used')} "
            f"available={rate.get('available')} "
            f"expiry={rate.get('expiry')}"
        )
        if int(stage["missing_symbol_count"]) > 0:
            print(
                "    missing: "
                + json.dumps(stage["missing_symbols"], sort_keys=True)
            )
        if int(stage["unexpected_symbol_count"]) > 0:
            print(
                "    unexpected: "
                + json.dumps(stage["unexpected_symbols"], sort_keys=True)
            )

    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: diagnostic only; current provider policy is unchanged "
        "and streaming remains unqualified"
    )
    return 0 if report["status"] != "FAIL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
