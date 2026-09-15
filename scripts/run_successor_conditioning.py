from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.successor_conditioning_analysis import (
    run_successor_conditioning_analysis,
)
from packages.core.execution_profile import detect_total_memory_bytes
from packages.core.successor_execution_profile import (
    resolve_successor_research_execution_profile,
)
from packages.strategies.successor_conditioning_contract import (
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze the exact accepted successor DEVELOPMENT standalone artifacts "
            "under the frozen training-only walk-forward conditioning contract."
        )
    )
    parser.add_argument(
        "--authorize-development-conditioning",
        action="store_true",
        help=(
            "Required explicit acknowledgement that this opens DEVELOPMENT-only "
            "strategy/condition aggregates. It does not open master, future blind, "
            "confluence, PAPER, LIVE, or promotion authority."
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_conditioning:
        raise SystemExit(
            "Refusing to open successor conditioning evidence without "
            "--authorize-development-conditioning"
        )
    profile = resolve_successor_research_execution_profile(
        logical_cpus=os.cpu_count() or 1,
        total_memory_bytes=detect_total_memory_bytes(),
    )
    print("ATLAS Successor DEVELOPMENT Conditioning / Specialist Router Analysis", flush=True)
    print(f"  conditioning fingerprint: {SUCCESSOR_CONDITIONING_FINGERPRINT}", flush=True)
    print(
        "  authority: completed DEVELOPMENT standalone artifacts only; "
        "consumed master/future blind/provider/broker/PAPER/LIVE/promotion/confluence forbidden",
        flush=True,
    )
    print(
        f"  execution profile: {profile.workers} workers x "
        f"{profile.duckdb_threads_per_worker} DuckDB thread",
        flush=True,
    )
    report = run_successor_conditioning_analysis(PROJECT_ROOT, execution_profile=profile)
    overall = report["selector_summary"]["overall"]
    print("\nSUCCESSOR CONDITIONING: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(f"  normalized opportunities: {int(report['normalized']['record_count']):,}", flush=True)
    print(f"  walk-forward folds: {int(report['fold_count'])}", flush=True)
    print(
        "  eligible test opportunities / research-selected / comparable: "
        f"{int(overall['test_eligible_opportunities']):,} / "
        f"{int(overall['selected_opportunities']):,} / "
        f"{int(overall['selected_comparable']):,}",
        flush=True,
    )
    abstention = overall.get("abstention_rate_among_eligible")
    print(
        "  abstention among eligible: "
        + ("n/a" if abstention is None else f"{float(abstention):.2%}"),
        flush=True,
    )
    primary = overall.get("selected_mean_primary_net_return")
    stress = overall.get("selected_mean_stress_net_return")
    print(
        "  selected mean primary / stress net return: "
        + ("n/a" if primary is None else f"{float(primary):.6%}")
        + " / "
        + ("n/a" if stress is None else f"{float(stress):.6%}"),
        flush=True,
    )
    print(
        "  B35-inspired challengers: DEVELOPMENT diagnostic/training evidence only; "
        "cannot self-validate on DEVELOPMENT",
        flush=True,
    )
    print("  confluence opened: false", flush=True)
    print("  promotion authority: false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
