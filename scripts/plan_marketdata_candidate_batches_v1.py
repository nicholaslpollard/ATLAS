from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_batch_plan_v1 import (
    CandidateBatchPlanError,
    plan_candidate_chain_batches,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline PIT-safe historical-option chain batch planner (zero provider reads)."
    )
    parser.add_argument("--opportunities", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.opportunities.read_text(encoding="utf-8"))
        plan = plan_candidate_chain_batches(payload)
        settings = load_settings(PROJECT_ROOT, "development")
        path = (
            args.output.resolve()
            if args.output is not None
            else settings.resolved_path("data/options/manifests/marketdata_candidate_batch_plan_v1.json")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(plan, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError, CandidateBatchPlanError) as exc:
        print(f"PLAN BLOCKED: {type(exc).__name__}: {exc}")
        return 3

    print("ATLAS MarketData Candidate Chain Batch Plan V1")
    print(f"  opportunity count: {plan['opportunities']}")
    print(f"  shared historical-chain requests: {plan['shared_chain_requests']}")
    print(f"  minimum historical-chain credits (not a charge guarantee): {plan['minimum_historical_chain_credits']}")
    print("  provider reads: 0")
    print("  broker reads/writes: 0")
    print("  historical option P&L authority: false")
    print(f"  plan fingerprint: {plan['plan_fingerprint']}")
    print(f"  output: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
