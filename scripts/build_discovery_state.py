from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.discovery.persistence import DiscoveryStateManager


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Persist Phase 8 NORMAL/WATCH/WARM/HOT discovery state with hysteresis"
    )
    parser.add_argument("--date", dest="as_of_date", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    result = DiscoveryStateManager(load_settings(PROJECT_ROOT, "development")).build(args.as_of_date)
    print("ATLAS Phase 8 Discovery State")
    print(f"  as-of date:             {result.as_of_date}")
    print(f"  records:                {result.record_count:,}")
    print(f"  previous session:       {result.previous_session_date or 'none'}")
    print(f"  continuity used:        {result.continuity_used}")
    print(f"  idempotent skip:        {result.skipped}")
    print(f"  wall time:              {result.wall_seconds:.3f}s")
    print("  raw states:")
    for key, value in sorted(result.raw_state_counts.items()):
        print(f"    {key:<10} {value:>8,}")
    print("  effective states:")
    for key, value in sorted(result.effective_state_counts.items()):
        print(f"    {key:<10} {value:>8,}")
    print("  transitions:")
    for key, value in sorted(result.transition_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"    {key:<30} {value:>8,}")
    print(f"  dependency fingerprint: {result.dependency_fingerprint}")
    print(f"  snapshot SHA-256:       {result.snapshot_sha256}")
    print(f"  snapshot:               {result.snapshot_path}")
    print(f"  manifest:               {result.manifest_path}")
    print("  result:                 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
