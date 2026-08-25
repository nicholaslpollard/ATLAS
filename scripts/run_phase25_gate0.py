from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate0 import Phase25Gate0Inventory  # noqa: E402
from packages.backtesting.phase25_policy import phase25_gate0_policy_fingerprint  # noqa: E402
from packages.core.settings import load_settings  # noqa: E402


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS Phase25 Gate0 provider-free production-path feasibility inventory"
    )
    parser.add_argument("--through", type=_date, required=True, help="final exchange session YYYY-MM-DD")
    args = parser.parse_args()

    settings = load_settings()
    report = Phase25Gate0Inventory(settings).run(through_date=args.through)
    coverage = report["coverage"]

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 0")
    print(f"Phase 25 Gate0 policy: {phase25_gate0_policy_fingerprint()}")
    print(f"Replay origin: {report['replay_origin']}")
    print(f"Through session: {report['through_date']}")
    print(f"Replay sessions inventoried: {report['replay_session_count']}")
    print(f"Market daily lineage sessions inventoried: {report['market_daily_session_count']}")
    print(f"Report: {report['report_path']}")
    print("Scope: LOCAL FEASIBILITY INVENTORY ONLY")
    print("Strategy returns/protected evidence: DISABLED / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/support authority: NONE")
    print()
    print("Core local coverage:")
    for key in (
        "canonical_1d",
        "derived_4h",
        "derived_1h",
        "features_1d",
        "features_4h",
        "features_1h",
        "feature_manifests_triplet",
        "reference_pair",
        "universe_pair",
        "discovery_materialized",
        "market_regime_pair",
        "ticker_regime_pair",
    ):
        item = coverage[key]
        print(f"  {key}: {item['present_sessions']}/{item['total_sessions']}")
    market = report["market_daily_feature_manifest_coverage"]
    print(
        "Market daily feature lineage: "
        f"{market['present_sessions']}/{market['total_sessions']}"
    )
    print(f"Identity inputs complete: {report['identity_inputs_complete']}")
    print(
        "Universe sessions reconstructable from exact local reference: "
        f"{report['universe_reference_reconstructable_sessions']}"
    )
    print(f"Universe source blocked sessions: {report['universe_source_blocked_sessions']}")
    print(
        "Route-fidelity available/replayable sessions: "
        f"{report['route_fidelity_ready_sessions']}/{report['replay_session_count']}"
    )
    print("Ready ranges:")
    if report["route_fidelity_ready_ranges"]:
        for item in report["route_fidelity_ready_ranges"]:
            print(f"  {item['start']} -> {item['end']} ({item['sessions']} sessions)")
    else:
        print("  NONE")
    print("Blockers:")
    if report["blockers"]:
        for blocker in report["blockers"]:
            print(f"  - {blocker}")
    else:
        print("  NONE")
    print(f"Recommendation: {report['recommendation']}")
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
