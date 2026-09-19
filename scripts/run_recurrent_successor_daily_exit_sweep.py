from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    run_recurrent_successor_daily_exit_sweep,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep_contract import (
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
)
from packages.strategies.successor_conditioning_contract import (
    DEVELOPMENT_END,
    DEVELOPMENT_START,
)


def _date_value(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded DEVELOPMENT daily LONG recurrent STOP/TARGET/TIME "
            "policy sweep across the frozen 1/2/3/5 percent stop-target grid."
        )
    )
    parser.add_argument(
        "--authorize-development-exit-sweep",
        action="store_true",
        help=(
            "Required acknowledgement that this is post-result DEVELOPMENT exit "
            "research only. It grants no promotion, PAPER, or LIVE authority."
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
        default=date.fromisoformat(str(DEVELOPMENT_START)),
        help="Earliest signal session to include.",
    )
    parser.add_argument(
        "--end",
        type=_date_value,
        default=date.fromisoformat(str(DEVELOPMENT_END)),
        help="Latest signal session to include.",
    )
    parser.add_argument(
        "--policy-id",
        action="append",
        default=[],
        help="Optional exact successor strategy policy filter; repeat as needed.",
    )
    parser.add_argument(
        "--duckdb-threads",
        type=int,
        default=None,
        help="Optional DuckDB thread count for conditioning joins.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional output directory.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_exit_sweep:
        raise SystemExit(
            "Refusing to open the post-result DEVELOPMENT exit sweep without "
            "--authorize-development-exit-sweep"
        )

    print("ATLAS Recurrent Successor Daily Exit Policy Sweep", flush=True)
    print(
        f"  contract fingerprint: "
        f"{RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT}",
        flush=True,
    )
    print(
        f"  signal scope: {args.start.isoformat()} -> {args.end.isoformat()}",
        flush=True,
    )
    print("  initial equity: $" + f"{args.initial_equity:,.2f}", flush=True)
    print(
        "  policy grid: stop 1/2/3/5% x target 1/2/3/5% = 16 policies",
        flush=True,
    )
    print(
        "  collision rule: same-session STOP+TARGET => STOP (worst case)",
        flush=True,
    )
    print(
        "  gap rule: adverse stop gaps fill at session open; favorable target "
        "gaps receive no positive slippage beyond target",
        flush=True,
    )
    print(
        "  TIME exit: fifth entry-session regular close",
        flush=True,
    )
    print(
        "  portfolio: 10% current book equity per position; max 10 active/"
        "reserved; max 3 per family; one active/reserved ticker",
        flush=True,
    )
    print(
        "  authority: DEVELOPMENT tuning diagnostic only; no master/future/"
        "provider/broker/PAPER/LIVE/promotion",
        flush=True,
    )

    report = run_recurrent_successor_daily_exit_sweep(
        PROJECT_ROOT,
        initial_equity=args.initial_equity,
        start_session=args.start,
        end_session=args.end,
        policy_ids=tuple(args.policy_id),
        output_root=args.output_root,
        duckdb_threads=args.duckdb_threads,
    )

    results = list(report["policy_results"])
    print("\nDAILY EXIT POLICY SWEEP: COMPLETE", flush=True)
    print(f"  run fingerprint: {report['run_fingerprint']}", flush=True)
    print(
        f"  usable daily LONG cases: "
        f"{int(report['usable_daily_long_cases']):,}",
        flush=True,
    )
    print("\n  Diagnostic policy comparison:", flush=True)
    print(
        "  STOP  TARGET    RETURN    MARKED_DD   BOOK_DD   TRADES   "
        "STOP/TARGET/TIME",
        flush=True,
    )
    for item in sorted(
        results,
        key=lambda value: float(value["total_return"]),
        reverse=True,
    ):
        exits = dict(item.get("exit_dispositions") or {})
        print(
            f"  {float(item['stop_fraction']):>4.0%}  "
            f"{float(item['target_fraction']):>6.0%}  "
            f"{float(item['total_return']):>8.2%}  "
            f"{float(item['maximum_marked_equity_drawdown']):>10.2%}  "
            f"{float(item['maximum_book_equity_drawdown']):>8.2%}  "
            f"{int(item['completed_positions']):>7,}   "
            f"{int(exits.get('STOP', 0))}/"
            f"{int(exits.get('TARGET', 0))}/"
            f"{int(exits.get('TIME', 0))}",
            flush=True,
        )

    print(
        "\n  IMPORTANT: ordering above is diagnostic only. The highest 2025 "
        "return is not automatically promoted; we will inspect return, marked "
        "drawdown, trade count, collision/gap exposure, and then test bounded "
        "candidates across other DEVELOPMENT regimes.",
        flush=True,
    )
    summary_path = (
        Path(args.output_root).resolve() / "sweep_summary.json"
        if args.output_root is not None
        else None
    )
    if summary_path is not None:
        print("  summary: " + str(summary_path), flush=True)
    else:
        print(
            "  summary location is recorded in the run output tree under "
            "data/research/recurrent_successor_daily_exit_sweep/",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
