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
from packages.features.historical_materializer import (
    FeatureBootstrapRequired,
    HistoricalFeatureMaterializer,
)
from packages.features.materialization import ACTIVE_FEATURE_PERSISTENCE_POLICY


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize exact stateful ATLAS historical feature partitions."
    )
    parser.add_argument("--timeframe", choices=["1d", "4h", "1h", "15m", "1m"], required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--bootstrap-from-empty",
        action="store_true",
        help="Required for a first build at the chosen ATLAS feature-history origin.",
    )
    parser.add_argument(
        "--allow-candidate",
        action="store_true",
        help="Allow persistence for a benchmark-candidate timeframe such as 1h.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Only identify materialized sessions whose source SHA/contract is stale.",
    )
    parser.add_argument(
        "--replay-from",
        type=date.fromisoformat,
        default=None,
        help="Replay from the latest monthly state anchor before this corrected session.",
    )
    parser.add_argument(
        "--history-start",
        type=date.fromisoformat,
        default=None,
        help="ATLAS feature-history origin; required if replay may need to fall back to genesis.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timeframe = Timeframe(args.timeframe)
    policy_tier = ACTIVE_FEATURE_PERSISTENCE_POLICY.tier_for(timeframe)
    settings = load_settings(PROJECT_ROOT)
    service = HistoricalFeatureMaterializer(settings)

    print("ATLAS Historical Feature Materializer")
    print(f"  timeframe:     {timeframe.value}")
    print(f"  policy tier:   {policy_tier}")
    print(f"  range:         {args.start} -> {args.end}")

    if args.audit_only:
        stale = service.stale_source_sessions(
            timeframe=timeframe,
            start=args.start,
            end=args.end,
        )
        print(f"  stale sessions: {len(stale):,}")
        for trading_date in stale[:50]:
            print(f"    {trading_date}")
        if len(stale) > 50:
            print(f"    ... and {len(stale) - 50:,} more")
        return 1 if stale else 0

    if args.replay_from is not None:
        if args.history_start is None:
            raise SystemExit("--history-start is required with --replay-from")
        result = service.replay_from_correction(
            timeframe=timeframe,
            corrected_date=args.replay_from,
            end=args.end,
            history_start=args.history_start,
            allow_candidate=args.allow_candidate,
        )
    else:
        try:
            result = service.materialize_range(
                timeframe=timeframe,
                start=args.start,
                end=args.end,
                bootstrap_from_empty=args.bootstrap_from_empty,
                allow_candidate=args.allow_candidate,
            )
        except FeatureBootstrapRequired as exc:
            print(f"  bootstrap required: {exc}")
            return 2

    print("ATLAS feature materialization result")
    print(f"  effective range:    {result.effective_start} -> {result.effective_end}")
    print(f"  sessions processed: {result.sessions_processed:,}")
    print(f"  rows processed:     {result.rows_processed:,}")
    print(f"  checkpoint as-of:   {result.checkpoint_as_of}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
