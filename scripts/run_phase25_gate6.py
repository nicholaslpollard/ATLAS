from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate6 import Phase25Gate6Error
from packages.backtesting.phase25_gate6_policy import phase25_gate6_policy_fingerprint
from packages.backtesting.phase25_gate6_repair import Phase25Gate6SafeDiscoveryReconstruction
from packages.backtesting.phase25_gate6_validation import (
    Phase25Gate6IndependentValidationError,
    Phase25Gate6IndependentValidator,
)
from packages.core.settings import load_settings


def _progress(*, index: int, total: int, session: date, summary: dict[str, object]) -> None:
    if index == 1 or index == total or index % 25 == 0:
        print(
            f"Progress: {index}/{total} sessions | session={session} | "
            f"universe={summary['universe_routed']} | broad_ready={summary['foundation_broad_ready']} | "
            f"scored={summary['scored']} | warm_hot_directional={summary['warm_hot_directional']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase25 Gate6 provider-free Phase7/discovery chronological reconstruction. "
            "Materializes missing stateless historical artifacts, preflights all existing artifacts "
            "before builders, and writes research-only discovery state."
        )
    )
    parser.add_argument("--through", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 6")
    print(f"Phase 25 Gate6 policy: {phase25_gate6_policy_fingerprint()}")
    print("Replay origin: 2021-08-16")
    print(f"Through session: {args.through}")
    print("Scope: PROVIDER-FREE PHASE7 + DISCOVERY CHRONOLOGICAL RECONSTRUCTION")
    print("Existing artifact handling: PREFLIGHT BEFORE ANY BUILDER / NO OVERWRITE")
    print("Operational discovery-state writes: DISABLED")
    print("Regime routing / strategy returns / strategy rules: DISABLED / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/support authority: NONE")

    settings = load_settings()
    try:
        report = Phase25Gate6SafeDiscoveryReconstruction(settings).run(
            through_date=args.through,
            progress_callback=_progress,
        )
        validation = Phase25Gate6IndependentValidator(settings).run(through_date=args.through)
    except (Phase25Gate6Error, Phase25Gate6IndependentValidationError, FileNotFoundError, ValueError) as exc:
        print("Reconstruction status: BLOCKED")
        print(f"Reason: {exc}")
        print("Provider calls attempted by Gate6: NO")
        print("Do not delete or overwrite a partial historical artifact set; reconcile the reported path first.")
        return 2

    print("Reconstruction status: COMPLETE")
    print(f"Report: {report['report_path']}")
    print(f"Independent validation: {validation['report_path']}")
    print(f"Replay sessions: {report['replay_session_count']}")
    print(f"Existing artifacts preserved: {report['existing_artifact_counts']}")
    print(f"New historical artifacts materialized: {report['newly_materialized_artifact_counts']}")
    print(f"Reconciliation events: {report.get('reconciliation_event_count', 0)}")
    print(f"Effective state row counts: {report['effective_state_row_counts']}")
    print(f"WARM/HOT direction counts: {report['warm_hot_direction_counts']}")
    print(f"WARM/HOT directional population rows: {report['warm_hot_directional_population_rows']}")
    print(f"Provider reads/writes: {report['provider_reads']} / {report['provider_writes']}")
    print(f"Operational discovery-state writes: {report['operational_discovery_state_writes']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(f"Order/PAPER/LIVE writes: {report['order_writes']} / {report['paper_submits']} / {report['live_writes']}")
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Independent validation pass: {validation['pass']}")
    print(f"Pass: {report['pass'] and validation['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
