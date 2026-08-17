from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.features.continuity import FeatureContinuityVerifier
from packages.features.lake_audit import PERMANENT_FEATURE_TIMEFRAMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify persisted historical feature checkpoints can hydrate and continue "
            "through the live-compatible incremental engine without discontinuity."
        )
    )
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument(
        "--timeframe",
        choices=["all", "1d", "4h", "1h"],
        default="all",
    )
    parser.add_argument("--atol", type=float, default=1e-10)
    parser.add_argument("--rtol", type=float, default=1e-10)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    verifier = FeatureContinuityVerifier(settings)
    if args.timeframe == "all":
        timeframes = PERMANENT_FEATURE_TIMEFRAMES
    else:
        timeframes = (Timeframe(args.timeframe),)

    print("ATLAS Historical -> Incremental Feature Continuity")
    print(f"  target date: {args.date}")
    print(f"  exact symbol: {args.symbol}")
    passed = True
    for timeframe in timeframes:
        result = verifier.verify(
            timeframe=timeframe,
            target_date=args.date,
            symbol=args.symbol,
            atol=args.atol,
            rtol=args.rtol,
        )
        print(f"\n  {timeframe.value}")
        print(f"    anchor:            {result.anchor_date}")
        print(f"    replay sessions:   {result.replay_sessions:,}")
        print(f"    replay source rows:{result.replay_source_rows:>9,}")
        print(f"    target rows:       {result.target_rows:,}")
        print(f"    features compared: {result.features_compared}")
        print(f"    key match:         {'PASS' if result.key_match else 'FAIL'}")
        print(f"    maximum abs diff:  {result.maximum_abs_diff:.3e}")
        print(f"    result:            {'PASS' if result.passed else 'FAIL'}")
        if result.failed_features:
            print("    failed features:")
            for name in result.failed_features:
                print(f"      {name}")
        passed = passed and result.passed

    print("\nATLAS feature-state continuation result")
    print(f"  result: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
