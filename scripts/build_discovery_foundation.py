from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.discovery.filter_policy import (
    ACTIVE_DISCOVERY_FILTER_POLICY,
    DISCOVERY_FILTER_POLICY_VERSION,
)
from packages.discovery.scanner import (
    DISCOVERY_FOUNDATION_MANIFEST_VERSION,
    DiscoveryFoundationScanner,
)
from packages.schemas.candidate import DISCOVERY_CANDIDATE_CONTRACT_VERSION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase 8 data-health/activity discovery foundation."
    )
    parser.add_argument("--date", required=True, type=date.fromisoformat, dest="as_of_date")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(PROJECT_ROOT, "development")
    result = DiscoveryFoundationScanner(settings).build(args.as_of_date)

    print("ATLAS Phase 8 Discovery Foundation")
    print(f"  as-of date:                  {result.as_of_date}")
    print(f"  candidate contract:          {DISCOVERY_CANDIDATE_CONTRACT_VERSION}")
    print(f"  filter policy:               {DISCOVERY_FILTER_POLICY_VERSION}")
    print(f"  policy fingerprint:          {ACTIVE_DISCOVERY_FILTER_POLICY.fingerprint}")
    print(f"  manifest contract:           {DISCOVERY_FOUNDATION_MANIFEST_VERSION}")
    print(f"  minimum dollar volume:       ${ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume:,.0f}")
    print("  minimum share price:         none")
    print(f"  source universe:             {result.source_universe_count:,}")
    print(f"  data-health pass:            {result.data_health_pass_count:,}")
    print(f"  activity pass:               {result.activity_pass_count:,}")
    print(f"  broad discovery ready:       {result.broad_discovery_ready_count:,}")
    print(f"  mandatory routes:            {result.mandatory_route_count:,}")
    print(f"  consideration required:      {result.consideration_required_count:,}")
    print(f"  intraday ready:              {result.intraday_ready_count:,}")
    print(f"  idempotent skip:             {result.skipped}")
    print(f"  wall time:                   {result.wall_seconds:.3f}s")

    print("  activity tiers:")
    for key, value in result.activity_tier_counts.items():
        print(f"    {key:<18} {value:>8,}")

    print("  decision reasons:")
    for key, value in result.reason_counts.items():
        print(f"    {key:<34} {value:>8,}")

    print("  broad-ready security types:")
    for key, value in result.security_type_counts.items():
        print(f"    {key:<12} {value:>8,}")

    print(f"  dependency fingerprint:      {result.dependency_fingerprint}")
    print(f"  snapshot SHA-256:            {result.snapshot_sha256}")
    print(f"  snapshot:                    {result.snapshot_path}")
    print(f"  manifest:                    {result.manifest_path}")
    print("  result:                      PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
