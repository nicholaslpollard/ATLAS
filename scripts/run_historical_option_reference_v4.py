from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_option_reference_v4 import (
    run_historical_option_reference_v4_acquisition,
)
from packages.data.historical_option_reference_v4_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    CORRECTION_SELECTION_POLICY,
    HISTORICAL_OPTION_REFERENCE_V4_CONTRACT_FINGERPRINT,
    REFERENCE_AS_OF_DATE,
    reference_partitions,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire Historical Option Reference V4 with point-in-time list+overview "
            "same-rank identity resolution and structural-reference authority only."
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
    print("ATLAS Historical Option Reference V4 Acquisition")
    print(
        "  contract fingerprint: "
        f"{HISTORICAL_OPTION_REFERENCE_V4_CONTRACT_FINGERPRINT}"
    )
    print(f"  reference as-of date: {REFERENCE_AS_OF_DATE.isoformat()}")
    print(
        "  active expiration hard end: "
        f"{ACTIVE_HARD_END_EXCLUSIVE.isoformat()} exclusive"
    )
    print(f"  monthly partitions: {len(reference_partitions())}")
    print(f"  workers: {args.workers}")
    print(f"  max in-flight partitions: {args.workers}")
    print("  verified V3/V2/V1 raw reuse: enabled")
    print(f"  duplicate-version policy: {CORRECTION_SELECTION_POLICY}")
    print(
        "  same-rank conflict fallback: pre-expiration structural list + "
        "Contract Overview exact-current-row match; otherwise fail closed"
    )
    print(
        "  authority: structural reference acquisition only; "
        "no historical availability/deliverable/price or strategy/PAPER/LIVE authority"
    )

    summary = run_historical_option_reference_v4_acquisition(
        settings,
        workers=args.workers,
    )

    storage = summary["storage_after"]
    print("\nHISTORICAL OPTION REFERENCE V3: COMPLETE")
    print(f"  corpus fingerprint: {summary['corpus_fingerprint']}")
    print(f"  run fingerprint: {summary['run_fingerprint']}")
    print(f"  partitions: {int(summary['monthly_partitions']):,}")
    print(
        "  V4 reused / V3 raw rebuilt / V2 raw rebuilt / V1 raw rebuilt / provider acquired: "
        f"{int(summary['reused_verified_partitions']):,} / "
        f"{int(summary['rebuilt_from_verified_v3_raw_this_run']):,} / "
        f"{int(summary['rebuilt_from_verified_v2_raw_this_run']):,} / "
        f"{int(summary['rebuilt_from_verified_v1_raw_this_run']):,} / "
        f"{int(summary['provider_acquired_partitions_this_run']):,}"
    )
    print(
        "  historically resolved conflicts: "
        f"{int(summary['historically_resolved_conflicts']):,}"
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
        "  duplicate version rows: "
        f"{int(summary['duplicate_version_rows']):,}"
    )
    print(
        "  tickers with multiple versions: "
        f"{int(summary['tickers_with_multiple_versions']):,}"
    )
    print(
        "  exact duplicate rows: "
        f"{int(summary['exact_duplicate_rows']):,}"
    )
    print(
        "  selected contracts with explicit correction: "
        f"{int(summary['corrected_selected_contracts']):,}"
    )
    print(
        "  raw/version reconciliation: "
        f"{summary['raw_version_reconciliation']}"
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
            "historical_option_reference_v4_summary.json"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
