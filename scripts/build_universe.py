from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.schemas.universe import UNIVERSE_CONTRACT_VERSION
from packages.universe.eligibility import (
    ACTIVE_UNIVERSE_ELIGIBILITY_POLICY,
    UNIVERSE_ELIGIBILITY_POLICY_VERSION,
)
from packages.universe.manager import UNIVERSE_MANIFEST_VERSION, UniverseManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and persist an exact point-in-time ATLAS universe snapshot."
    )
    parser.add_argument("--date", required=True, type=date.fromisoformat, dest="as_of_date")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(PROJECT_ROOT, "development")
    result = UniverseManager(settings).build(args.as_of_date, force=args.force)

    print("ATLAS Phase 7 Universe Build")
    print(f"  as-of date:                  {result.as_of_date}")
    print(f"  universe contract:           {UNIVERSE_CONTRACT_VERSION}")
    print(f"  policy version:              {UNIVERSE_ELIGIBILITY_POLICY_VERSION}")
    print(f"  policy fingerprint:          {ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.fingerprint}")
    print(f"  manifest contract:           {UNIVERSE_MANIFEST_VERSION}")
    print(f"  source reference rows:       {result.source_row_count:,}")
    print(f"  source stable instruments:   {result.source_instrument_count:,}")
    print(f"  routed instruments:          {result.routed_instrument_count:,}")
    print(f"  discovery eligible:          {result.discovery_count:,}")
    print(f"  excluded audit rows:         {result.exclusion_count:,}")
    print(f"  position routes:             {result.position_count:,}")
    print(f"  watchlist routes:            {result.watchlist_count:,}")
    print(f"  custom routes:               {result.custom_count:,}")
    print(f"  idempotent skip:             {result.skipped}")
    print("  discovery security types:")
    for security_type, count in sorted(
        result.discovery_security_type_counts.items(), key=lambda item: (-item[1], item[0])
    ):
        print(f"    {security_type:<12} {count:>8,}")
    print("  decision reasons:")
    for reason, count in sorted(result.reason_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"    {reason:<30} {count:>8,}")
    print(f"  universe fingerprint:        {result.fingerprint}")
    print(f"  snapshot:                    {result.snapshot_path}")
    print(f"  exclusion audit:             {result.exclusion_path}")
    print(f"  manifest:                    {result.manifest_path}")
    print("  result:                      PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
