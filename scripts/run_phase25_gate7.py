from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate7 import Phase25Gate7Error, Phase25Gate7RouteContextReplay
from packages.backtesting.phase25_gate7_policy import phase25_gate7_policy_fingerprint
from packages.backtesting.phase25_gate7_validation import (
    Phase25Gate7IndependentValidationError,
    Phase25Gate7IndependentValidator,
)
from packages.core.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase25 Gate7 provider-free exact-PIT market/ticker route-context replay. "
            "Runs the production StrategyRouter only; strategy rules and returns remain disabled."
        )
    )
    parser.add_argument("--through", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 7")
    print(f"Phase 25 Gate7 policy: {phase25_gate7_policy_fingerprint()}")
    print("Replay origin: 2021-08-16")
    print(f"Through session: {args.through}")
    print("Scope: PROVIDER-FREE EXACT-PIT MARKET + TICKER ROUTE CONTEXT")
    print("Sector mapping: UNAVAILABLE / NONBLOCKING")
    print("Operational regime writes: DISABLED")
    print("Strategy router: ENABLED")
    print("Strategy rule evaluation / returns / protected evidence: DISABLED / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/support authority: NONE")

    settings = load_settings()
    try:
        report = Phase25Gate7RouteContextReplay(settings).run(through_date=args.through)
        validation = Phase25Gate7IndependentValidator(settings).run(through_date=args.through)
    except (
        Phase25Gate7Error,
        Phase25Gate7IndependentValidationError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        print("Route-context status: BLOCKED")
        print(f"Reason: {exc}")
        print("Provider calls attempted by Gate7: NO")
        return 2

    print("Route-context status: COMPLETE")
    print(f"Report: {report['report_path']}")
    print(f"Independent validation: {validation['report_path']}")
    print(f"Gate6 WARM/HOT directional rows: {report['gate6_population_rows']}")
    print(f"Exact PIT ticker intervals: {report['exact_pit_interval_count']}")
    print(f"Ticker raw/persisted history rows: {report['ticker_raw_history_rows']} / {report['ticker_persisted_history_rows']}")
    print(f"Discovery direction counts: {report['discovery_direction_counts']}")
    print(f"Market state counts: {report['market_state_counts']}")
    print(f"Ticker state counts: {report['ticker_state_counts']}")
    print(f"Identity quality counts: {report['identity_quality_counts']}")
    print(f"Route decision rows: {report['route_decision_rows']}")
    print(f"Market-compatible candidates: {report['market_route_compatible_candidates']}")
    print(f"Ticker-compatible candidates: {report['ticker_route_compatible_candidates']}")
    print(f"Fully route-eligible candidates: {report['fully_route_eligible_candidates']}")
    print(f"Eligible route decisions: {report['eligible_route_decisions']}")
    print(f"Provider reads/writes: {report['provider_reads']} / {report['provider_writes']}")
    print(f"Operational regime writes: {report['operational_regime_writes']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(f"Order/PAPER/LIVE writes: {report['order_writes']} / {report['paper_submits']} / {report['live_writes']}")
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Independent validation pass: {validation['pass']}")
    print(f"Pass: {report['pass'] and validation['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
