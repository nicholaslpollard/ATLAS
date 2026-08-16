from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.live.reconciliation import LiveFinalizationReconciler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare provisional Massive WebSocket minute bars with finalized ATLAS canonical 1m data."
    )
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = LiveFinalizationReconciler(load_settings(PROJECT_ROOT)).reconcile(args.date)
    print(f"ATLAS live/final reconciliation {args.date}")
    print(f"  live bars:            {result.live_bar_count:,}")
    print(f"  canonical bars:       {result.canonical_bar_count:,}")
    print(f"  matched keys:         {result.matched_key_count:,}")
    print(f"  exact values:         {result.exact_match_count:,}")
    print(f"  corrected values:     {result.value_mismatch_count:,}")
    print(f"  live-only keys:       {result.live_only_key_count:,}")
    print(f"  canonical-only keys:  {result.canonical_only_key_count:,}")
    print(f"  canonical authority:  true")
    print(f"  report:               {Path(result.report_path or '').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
