from __future__ import annotations

"""Inspect real 2021–2026 strategy-lab scope without a single provider request."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.simulation.multiyear_research_scope_v1 import (
    MultiYearScopeError, plan_multiyear_scope,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS 2021-2026 stock/news/options laboratory scope (offline)"
    )
    parser.add_argument("--as-of-utc", help="Optional aware ISO-8601 timestamp")
    args = parser.parse_args()
    print("ATLAS Six-Year Integrated Simulator Scope — OFFLINE", flush=True)
    print("  Provider requests 0; paid acquisition authority NONE", flush=True)
    try:
        asof = (datetime.fromisoformat(args.as_of_utc)
                if args.as_of_utc else datetime.now(UTC))
        plan = plan_multiyear_scope(as_of_utc=asof)
        print(f"  target: {plan['research_start']} through {plan['research_end']}", flush=True)
        print(f"  rolling Starter floor: {plan['starter_five_year_floor']}", flush=True)
        for row in plan["year_slices"]:
            print(f"  {row['year']} {row['research_start']}..{row['research_end']}", flush=True)
            print(f"    Starter: {row['starter_coverage']} "
                  f"({row['starter_option_start']}..{row['starter_option_end']})", flush=True)
            print(f"    local option evidence: {row['known_local_option_scope']}", flush=True)
            print(f"    news: {row['news_scope']}", flush=True)
        print("  Greeks: model-derived from historical quote/underlying/rate/dividend inputs "
              "only; never substitute missing bid/ask.", flush=True)
        print(f"  plan fingerprint: {plan['plan_fingerprint']}", flush=True)
        print("  Result is a research coverage plan, NOT a finished historical simulation.", flush=True)
        return 0
    except (MultiYearScopeError, ValueError) as exc:
        print(f"MULTIYEAR SCOPE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
