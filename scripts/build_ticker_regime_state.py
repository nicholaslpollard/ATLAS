from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_state_engine import TickerStateEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the accepted Phase 9 per-ticker regime state for one finalized session."
    )
    parser.add_argument("--date", required=True, help="Finalized/as-of session YYYY-MM-DD")
    return parser


def main(argv: list[str] | None = None) -> int:
    from datetime import date

    args = build_parser().parse_args(argv)
    as_of = date.fromisoformat(args.date)
    result = TickerStateEngine(load_settings(PROJECT_ROOT, "development")).build(as_of)

    print("ATLAS Phase 9 Gate 12 Ticker Regime State Materialization")
    print(f"  as-of session:                  {result.as_of_date}")
    print(f"  records:                        {result.record_count:,}")
    print(f"  raw state available:            {result.raw_state_available_count:,}")
    print(f"  confirmed persistence:          {result.confirmed_persistence_count:,}")
    print(f"  history status:                 {result.history_status_counts}")
    print(f"  persistence status:             {result.persistence_status_counts}")
    print(f"  risk modes:                     {result.risk_mode_counts}")
    print(f"  effective ticker states:        {result.effective_state_counts}")
    print(f"  dependency:                     {result.dependency_fingerprint}")
    print(f"  snapshot SHA-256:               {result.snapshot_sha256}")
    print(f"  idempotent skip:                {result.skipped}")
    print(f"  wall time:                      {result.wall_seconds:,.3f}s")
    print(f"  snapshot:                       {result.snapshot_path.resolve()}")
    print(f"  manifest:                       {result.manifest_path.resolve()}")
    print("  result:                         MATERIALIZED" if not result.skipped else "  result:                         CURRENT / SKIPPED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
