from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate2 import (  # noqa: E402
    Phase25Gate2ActiveOnlyEquivalence,
    Phase25Gate2Error,
)
from packages.backtesting.phase25_policy import phase25_gate2_policy_fingerprint  # noqa: E402
from packages.core.settings import load_settings  # noqa: E402


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase25 Gate2 provider-free active-only PIT discovery equivalence proof."
    )
    parser.add_argument("--through", type=_parse_date, required=True)
    args = parser.parse_args()

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 2")
    print(f"Phase 25 Gate2 policy: {phase25_gate2_policy_fingerprint()}")
    print(f"Through session: {args.through}")
    print("Scope: LOCAL ACTIVE-ONLY PIT DISCOVERY EQUIVALENCE ONLY")
    print("Strategy returns/protected evidence: DISABLED / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/support authority: NONE")

    try:
        report = Phase25Gate2ActiveOnlyEquivalence(load_settings()).run(
            through_date=args.through
        )
    except (Phase25Gate2Error, FileNotFoundError, ValueError) as exc:
        print(f"Gate 2 status: BLOCKED: {exc}")
        print("Provider reads/writes: 0 / 0")
        print("Broker reads/writes: 0 / 0")
        print("Order/PAPER/LIVE writes: 0 / 0 / 0")
        return 2

    print(f"Report: {report['report_path']}")
    print(f"PIT dates tested: {report['tested_reference_date_count']}")
    print(
        "Reference rows full / active / inactive: "
        f"{report['total_full_reference_rows']} / "
        f"{report['total_active_reference_rows']} / "
        f"{report['total_inactive_reference_rows']}"
    )
    print(
        "Observed row reduction using active-only: "
        f"{float(report['observed_row_reduction_fraction']) * 100:.2f}%"
    )
    print("Per-date equivalence:")
    for item in report["date_equivalence"]:
        print(
            "  "
            f"{item['as_of_date']}: "
            f"full={item['computed_full_discovery_members']} "
            f"active_only={item['computed_active_only_discovery_members']} "
            f"materialized={item['materialized_discovery_members']} "
            f"full_vs_active_mismatch={item['full_vs_active_only_mismatch_count']} "
            f"active_vs_materialized_mismatch={item['active_only_vs_materialized_mismatch_count']} "
            f"pass={item['pass_equivalence']}"
        )
    print(f"All dates equivalent: {report['all_dates_equivalent']}")
    print(f"Recommendation: {report['recommendation']}")
    print("Active-only acquisition authority: NONE / NOT GRANTED BY GATE2")
    print(f"Protected strategy evidence reads: {report['protected_strategy_evidence_reads']}")
    print(f"Provider reads/writes: {report['provider_reads']} / {report['provider_writes']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(
        "Order/PAPER/LIVE writes: "
        f"{report['order_writes']} / {report['paper_submits']} / {report['live_writes']}"
    )
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
