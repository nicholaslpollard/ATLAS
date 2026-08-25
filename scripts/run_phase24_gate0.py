from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase24_gate0 import Phase24Gate0Diagnostic, Phase24Gate0Error
from packages.backtesting.phase24_policy import PHASE24_GATE0_AS_OF, phase24_policy_fingerprint
from packages.core.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase 24 Gate 0 provider-free forensic strategy diagnostic. "
            "This runner has no provider, broker, order, PAPER, LIVE, or support-replacement authority."
        )
    )
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings()
    diagnostic = Phase24Gate0Diagnostic(settings)
    try:
        result = diagnostic.run(as_of_date=args.as_of)
    except (Phase24Gate0Error, ValueError) as exc:
        print("Phase 24 Gate 0 status: BLOCKED")
        print(f"Reason: {exc}")
        print("External/provider/broker calls attempted: NO")
        raise SystemExit(2) from None

    summary = dict(result["counterfactual_summary"])
    print("ATLAS Phase 24 Strategy Evidence Challenger — Gate 0")
    print(f"Phase 24 policy: {phase24_policy_fingerprint()}")
    print(f"Locked as-of session: {PHASE24_GATE0_AS_OF}")
    print(f"Report: {result['report_path']}")
    print(f"Accepted current WARM/HOT directional cases: {result['accepted_current_considered']}")
    print(f"Accepted authoritative promotions: {result['accepted_current_promoted']}")
    print(f"Counterfactual eligible route evaluations: {summary['eligible_route_evaluations']}")
    print(f"Counterfactual incumbent rule fires: {summary['counterfactual_fires']}")
    print(f"Candidates with at least one counterfactual fire: {summary['candidates_with_counterfactual_fire']}")
    print(f"Support status counts: {result['support_status_counts']}")
    print("Counterfactual firing authority: NONE / DIAGNOSTIC ONLY")
    print("Provider reads/writes: 0 / 0")
    print("Broker reads/writes: 0 / 0")
    print("Order/PAPER/LIVE writes: 0 / 0 / 0")
    print("Phase 11 support writes: 0")
    print(f"Pass: {result['pass']}")


if __name__ == "__main__":
    main()
