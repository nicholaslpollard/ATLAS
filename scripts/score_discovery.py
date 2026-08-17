from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.discovery.scoring import DiscoverySetupScanner


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the Phase 8 broad discovery population")
    parser.add_argument("--date", dest="as_of_date", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    result = DiscoverySetupScanner(load_settings(PROJECT_ROOT, "development")).build(args.as_of_date)
    print("ATLAS Phase 8 Discovery Scoring")
    print(f"  as-of date:             {result.as_of_date}")
    print(f"  scored instruments:     {result.scored_count:,}")
    print(f"  idempotent skip:        {result.skipped}")
    print(f"  wall time:              {result.wall_seconds:.3f}s")
    print("  states:")
    for key, value in sorted(result.state_counts.items()):
        print(f"    {key:<10} {value:>8,}")
    print("  directions:")
    for key, value in sorted(result.direction_counts.items()):
        print(f"    {key:<10} {value:>8,}")
    print("  scored timeframe coverage:")
    for key, value in sorted(result.timeframe_coverage_counts.items(), key=lambda item: int(item[0])):
        print(f"    {key} timeframe(s) {value:>8,}")
    print("  top setup families:")
    for key, value in sorted(result.top_setup_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"    {key:<24} {value:>8,}")
    print("  priority distribution:")
    for key, value in result.priority_quantiles.items():
        print(f"    {key:<4} {value:.6f}")
    print(f"  dependency fingerprint: {result.dependency_fingerprint}")
    print(f"  snapshot SHA-256:       {result.snapshot_sha256}")
    print(f"  snapshot:               {result.snapshot_path}")
    print(f"  manifest:               {result.manifest_path}")
    print("  result:                 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
