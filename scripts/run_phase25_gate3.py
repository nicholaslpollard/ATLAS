from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate3 import Phase25Gate3AcquisitionPlan, Phase25Gate3Error
from packages.backtesting.phase25_policy import phase25_gate3_policy_fingerprint
from packages.core.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase 25 Gate3 provider-free preregistration of the exact active-only "
            "Massive PIT reference acquisition scope. This command performs no provider reads."
        )
    )
    parser.add_argument("--through", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings()
    planner = Phase25Gate3AcquisitionPlan(settings)

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 3")
    print(f"Phase 25 Gate3 policy: {phase25_gate3_policy_fingerprint()}")
    print(f"Through session: {args.through}")
    print("Scope: PROVIDER-FREE ACTIVE-ONLY EXACT PIT ACQUISITION PREREGISTRATION")
    print("Provider acquisition authority: NONE / NOT GRANTED BY GATE3")
    print("Strategy returns/protected evidence: DISABLED / UNREAD")
    print("Broker/order/PAPER/LIVE/support authority: NONE")

    try:
        report = planner.run(through_date=args.through)
    except (Phase25Gate3Error, ValueError) as exc:
        print("Gate3 status: BLOCKED")
        print(f"Reason: {exc}")
        print("Provider calls attempted: NO")
        raise SystemExit(2) from None

    print(f"Report: {report['report_path']}")
    print(f"Replay sessions: {report['replay_session_count']}")
    print(f"Existing valid PIT reference sessions: {report['existing_valid_reference_session_count']}")
    print(f"  Full active+inactive existing: {report['existing_full_reference_session_count']}")
    print(f"  Active-only existing: {report['existing_active_only_reference_session_count']}")
    print(f"Exact active-only acquisition sessions: {report['acquisition_session_count']}")
    print(f"Earliest entitlement probe session: {report['entitlement_probe_session'] or 'NONE'}")
    print(
        "Observed pages/session at limit=1000: "
        f"{report['observed_pages_per_session_min']}–{report['observed_pages_per_session_max']}"
    )
    print(
        "Projected provider page requests: "
        f"{report['projected_provider_page_requests_min']}–{report['projected_provider_page_requests_max']}"
    )
    query = report["acquisition_query"]
    print(
        "Locked query: "
        f"GET {query['endpoint']} market={query['market']} active={str(query['active']).lower()} "
        f"order={query['order']} sort={query['sort']} limit={query['limit']} date=EXACT_SESSION_DATE"
    )
    print(f"Recommendation: {report['recommendation']}")
    print(f"Active-only acquisition authority: {report['active_only_reference_acquisition_authority']}")
    print(f"Protected strategy evidence reads: {report['protected_strategy_evidence_reads']}")
    print(f"Provider reads/writes: {report['provider_reads']} / {report['provider_writes']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(
        "Order/PAPER/LIVE writes: "
        f"{report['order_writes']} / {report['paper_submits']} / {report['live_writes']}"
    )
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Pass: {report['pass']}")


if __name__ == "__main__":
    main()
