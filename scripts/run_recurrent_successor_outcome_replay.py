from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.recurrent_successor_outcome_replay import (
    run_recurrent_successor_outcome_replay,
)
from packages.backtesting.recurrent_successor_outcome_replay_contract import (
    RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT,
)
from packages.strategies.successor_conditioning_contract import (
    DEVELOPMENT_END,
    DEVELOPMENT_START,
)


def _date_value(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "date must use YYYY-MM-DD"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay accepted successor walk-forward-selected DEVELOPMENT outcomes "
            "through the current recurrent account lifecycle. This is a long-only "
            "historical outcome-replay diagnostic, not PAPER/LIVE and not the later "
            "bar-level STOP/TARGET/TIME retest."
        )
    )
    parser.add_argument(
        "--authorize-development-replay",
        action="store_true",
        help=(
            "Required acknowledgement that this opens a new DEVELOPMENT portfolio "
            "diagnostic using already accepted successor outcome artifacts. It does "
            "not authorize master/future-blind reads, PAPER, LIVE, or promotion."
        ),
    )
    parser.add_argument(
        "--initial-equity",
        type=float,
        required=True,
        help="Explicit starting simulation equity in dollars.",
    )
    parser.add_argument(
        "--start",
        type=_date_value,
        default=date.fromisoformat(DEVELOPMENT_START),
        help="Earliest signal session to include (default: full DEVELOPMENT start).",
    )
    parser.add_argument(
        "--end",
        type=_date_value,
        default=date.fromisoformat(DEVELOPMENT_END),
        help="Latest signal session to include (default: full DEVELOPMENT end).",
    )
    parser.add_argument(
        "--policy-id",
        action="append",
        default=[],
        help=(
            "Optional exact successor policy id filter. Repeat to include multiple "
            "policies."
        ),
    )
    parser.add_argument(
        "--duckdb-threads",
        type=int,
        default=None,
        help=(
            "Optional DuckDB thread count for selected-opportunity/source joins. "
            "Default is hardware-aware and capped at 8."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional output directory; default is under the accepted conditioning root.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_replay:
        raise SystemExit(
            "Refusing to open the recurrent successor DEVELOPMENT portfolio replay "
            "without --authorize-development-replay"
        )

    print("ATLAS Recurrent Successor DEVELOPMENT Outcome Replay", flush=True)
    print(
        f"  contract fingerprint: {RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT}",
        flush=True,
    )
    print(
        f"  signal scope: {args.start.isoformat()} -> {args.end.isoformat()}",
        flush=True,
    )
    print("  initial equity: $" + f"{args.initial_equity:,.2f}", flush=True)
    if args.policy_id:
        print(
            "  policy filter: " + ", ".join(sorted(set(args.policy_id))),
            flush=True,
        )
    else:
        print("  policy filter: all successor policies", flush=True)
    print(
        "  authority: DEVELOPMENT-only accepted artifacts; master/future/provider/"
        "broker/PAPER/LIVE/promotion forbidden",
        flush=True,
    )
    print(
        "  current limitation: LONG stock outcomes only; SHORT selections are "
        "reported but not simulated because recurrent funding v1 has no short "
        "borrow/collateral model",
        flush=True,
    )

    report = run_recurrent_successor_outcome_replay(
        PROJECT_ROOT,
        initial_equity=args.initial_equity,
        start_session=args.start,
        end_session=args.end,
        policy_ids=tuple(args.policy_id),
        output_root=args.output_root,
        duckdb_threads=args.duckdb_threads,
    )

    print("\nRECURRENT SUCCESSOR OUTCOME REPLAY: COMPLETE", flush=True)
    print(f"  run fingerprint: {report['run_fingerprint']}", flush=True)
    print(
        f"  selected / supported LONG / unsupported SHORT: "
        f"{int(report['selected_opportunities']):,} / "
        f"{int(report['supported_long_selected']):,} / "
        f"{int(report['unsupported_short_selected']):,}",
        flush=True,
    )
    print(
        f"  admitted / completed positions: "
        f"{int(report['admitted_positions']):,} / "
        f"{int(report['completed_positions']):,}",
        flush=True,
    )
    print(
        "  final book equity: $"
        + f"{float(report['final_book_equity']):,.2f}",
        flush=True,
    )
    print(
        f"  total return: {float(report['total_return_on_initial_equity']):.4%}",
        flush=True,
    )
    print(
        "  maximum realized/book-equity drawdown: "
        f"{float(report['maximum_realized_book_equity_drawdown']):.4%}",
        flush=True,
    )
    print(
        "  peak active/reserved slots: "
        f"{int(report['peak_active_or_reserved_slots'])}",
        flush=True,
    )
    rejections = report.get("rejections") or {}
    print(
        "  rejections: "
        + (json.dumps(rejections, sort_keys=True) if rejections else "none"),
        flush=True,
    )
    print(
        "  note: this first campaign mode replays accepted outcomes through the "
        "current recurrent account. It is not yet a bar-level STOP/TARGET/TIME "
        "strategy retest and does not change strategy evidence or authority.",
        flush=True,
    )
    summary_path = (
        Path(str(report["artifacts"]["closed_trades"]["path"])).parent
        / "run_summary.json"
    )
    print("  summary: " + str(summary_path), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
