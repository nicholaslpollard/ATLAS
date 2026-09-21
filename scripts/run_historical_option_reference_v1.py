from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_option_reference_v1 import (
    run_historical_option_reference_v1_acquisition,
)
from packages.data.historical_option_reference_v1_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT,
    REFERENCE_AS_OF_DATE,
    reference_partitions,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire the frozen Massive Historical Option Reference V1 corpus "
            "as structural reference data only."
        )
    )
    parser.add_argument(
        "--authorize-source-acquisition",
        action="store_true",
        help="Required explicit authorization for provider source acquisition.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent expiration-month workers. Default: 4.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_source_acquisition:
        print(
            "Refusing source acquisition without "
            "--authorize-source-acquisition.",
            file=sys.stderr,
        )
        return 2

    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Historical Option Reference V1 Acquisition")
    print(
        "  contract fingerprint: "
        f"{HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT}"
    )
    print(f"  reference as-of date: {REFERENCE_AS_OF_DATE.isoformat()}")
    print(
        "  active expiration hard end: "
        f"{ACTIVE_HARD_END_EXCLUSIVE.isoformat()} exclusive"
    )
    print(f"  monthly partitions: {len(reference_partitions())}")
    print(f"  workers: {args.workers}")
    print(
        "  authority: structural reference acquisition only; "
        "no historical availability/deliverable/price or strategy/PAPER/LIVE authority"
    )

    summary = run_historical_option_reference_v1_acquisition(
        settings,
        workers=args.workers,
    )

    storage = summary["storage_after"]
    print("\nHISTORICAL OPTION REFERENCE V1: COMPLETE")
    print(f"  corpus fingerprint: {summary['corpus_fingerprint']}")
    print(f"  run fingerprint: {summary['run_fingerprint']}")
    print(f"  partitions: {int(summary['monthly_partitions']):,}")
    print(
        "  reused/acquired this run: "
        f"{int(summary['reused_verified_partitions']):,} / "
        f"{int(summary['acquired_partitions_this_run']):,}"
    )
    print(
        "  raw provider records: "
        f"{int(summary['raw_provider_records']):,}"
    )
    print(
        "  normalized unique contracts: "
        f"{int(summary['normalized_unique_contracts']):,}"
    )
    print(
        "  duplicate ticker rows: "
        f"{int(summary['duplicate_ticker_rows']):,}"
    )
    print(
        "  storage: "
        f"{float(storage['options_reference_usage_gib']):.3f} / "
        f"{float(storage['options_reference_quota_gib']):.2f} GiB reference / "
        f"{float(storage['disk_free_gib']):.2f} GiB disk free"
    )
    print(
        "  summary: "
        + str(
            PROJECT_ROOT
            / "data/options/manifests/massive/"
            "historical_option_reference_v1_summary.json"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
