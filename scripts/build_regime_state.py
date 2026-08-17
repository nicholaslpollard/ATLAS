from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.persistence_policy import (
    REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
    REGIME_SELECTED_CONFIRMATION_SESSIONS,
)
from packages.regimes.state_engine import (
    REGIME_STATE_POLICY_CONTRACT_VERSION,
    REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
    RegimeStateEngine,
)
from packages.regimes.threshold_policy import (
    REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
    REGIME_HISTORY_ORIGIN_DATE,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
    REGIME_THRESHOLD_POLICY_NAME,
    REGIME_THRESHOLD_TRAINING_SESSIONS,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the accepted Phase 9 market + sector regime state"
    )
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    result = RegimeStateEngine(load_settings(PROJECT_ROOT, "development")).build(args.as_of)
    snapshot = json.loads(result.snapshot_path.read_text(encoding="utf-8"))

    print("ATLAS Phase 9 Market/Sector Regime State")
    print(f"  state policy contract:      {REGIME_STATE_POLICY_CONTRACT_VERSION}")
    print(f"  snapshot contract:          {REGIME_STATE_SNAPSHOT_CONTRACT_VERSION}")
    print(f"  threshold policy contract:  {REGIME_THRESHOLD_POLICY_CONTRACT_VERSION}")
    print(f"  persistence contract:       {REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION}")
    print(f"  breadth population:         {REGIME_BREADTH_POPULATION_CONTRACT_VERSION}")
    print(f"  as-of session:              {result.as_of_date}")
    print(f"  history origin:             {REGIME_HISTORY_ORIGIN_DATE}")
    print(f"  threshold memory:           {REGIME_THRESHOLD_POLICY_NAME}")
    print(f"  threshold seed:             {REGIME_THRESHOLD_TRAINING_SESSIONS} prior sessions")
    print(f"  persistence:                {REGIME_SELECTED_CONFIRMATION_SESSIONS}-session confirmation")
    print(f"  source 1d manifests:        {result.source_manifest_count:,}")
    print(f"  usable breadth sessions:    {result.usable_breadth_session_count:,}")
    print(f"  evaluation sessions:        {result.evaluation_session_count:,}")
    print(f"  first evaluation session:   {result.first_evaluation_date}")
    print(f"  sector observations:        {result.sector_observation_count:,}")

    market = snapshot["market"]
    raw = market["raw"]
    effective = market["effective"]
    print("  market state:")
    print(
        "    raw                        "
        f"{raw['composite']} | trend={raw['structure']} momentum={raw['momentum']} "
        f"participation={raw['participation']} vol={raw['volatility']} efficiency={raw['efficiency']}"
    )
    print(
        "    effective                  "
        f"{effective['composite']} | trend={effective['structure']} momentum={effective['momentum']} "
        f"participation={effective['participation']} vol={effective['volatility']} efficiency={effective['efficiency']}"
    )

    print("  effective sector proxy states:")
    for ticker, payload in snapshot["sectors"].items():
        state = payload["effective"]
        print(
            f"    {ticker:<5} {state['composite']:<12} trend={state['structure']:<11} "
            f"momentum={state['momentum']:<15} vol={state['volatility']:<8} "
            f"efficiency={state['efficiency']}"
        )

    counts = ", ".join(
        f"{state}={count:,}" for state, count in result.sector_state_counts.items()
    )
    print(f"  sector state counts:         {counts}")
    print(f"  dependency fingerprint:      {result.dependency_fingerprint}")
    print(f"  snapshot sha256:             {result.snapshot_sha256}")
    print(f"  snapshot:                    {result.snapshot_path}")
    print(f"  manifest:                    {result.manifest_path}")
    print(f"  wall time:                   {result.wall_seconds:.3f}s")
    print(f"  result:                      {'CURRENT' if result.skipped else 'MATERIALIZED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
