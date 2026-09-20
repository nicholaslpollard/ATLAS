from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.recurrent_successor_daily_exit_confirmation import (
    run_recurrent_successor_daily_exit_confirmation,
)
from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    CANDIDATE_EXIT_POLICIES,
    FORWARD_CONFIRMATION_WINDOW,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
    SOURCE_2025_SWEEP_RUN_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen chronologically-forward 2026 DEVELOPMENT confirmation "
            "for the two 2025 daily exit candidates."
        )
    )
    parser.add_argument(
        "--authorize-development-confirmation",
        action="store_true",
        help=(
            "Required acknowledgement that this is DEVELOPMENT confirmation "
            "only and grants no PAPER/LIVE/promotion authority."
        ),
    )
    parser.add_argument(
        "--initial-equity",
        type=float,
        required=True,
        help="Starting simulation equity in dollars.",
    )
    parser.add_argument(
        "--policy-id",
        action="append",
        default=[],
        help="Optional exact successor strategy policy filter; repeat as needed.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional candidate policy-process worker count.",
    )
    parser.add_argument(
        "--duckdb-threads",
        type=int,
        default=None,
        help="Optional DuckDB thread count for source preparation.",
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
    if not args.authorize_development_confirmation:
        raise SystemExit(
            "Refusing to run DEVELOPMENT confirmation without "
            "--authorize-development-confirmation"
        )

    start_session, end_session = FORWARD_CONFIRMATION_WINDOW
    print("ATLAS Recurrent Successor Daily Exit Candidate Confirmation", flush=True)
    print(
        "  contract fingerprint: "
        + RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
        flush=True,
    )
    print(
        "  source 2025 sweep fingerprint: "
        + SOURCE_2025_SWEEP_RUN_FINGERPRINT,
        flush=True,
    )
    print(
        f"  confirmation scope: {start_session.isoformat()} -> "
        f"{end_session.isoformat()}",
        flush=True,
    )
    print(
        "  frozen candidates: "
        + ", ".join(
            f"STOP {stop:.0%} / TARGET {target:.0%}"
            for stop, target in CANDIDATE_EXIT_POLICIES
        ),
        flush=True,
    )
    print(f"  initial equity: ${args.initial_equity:,.2f}", flush=True)
    print(
        "  authority: DEVELOPMENT-only forward confirmation; "
        "no promotion/PAPER/LIVE authority",
        flush=True,
    )

    report = run_recurrent_successor_daily_exit_confirmation(
        PROJECT_ROOT,
        initial_equity=args.initial_equity,
        policy_ids=tuple(args.policy_id),
        output_root=args.output_root,
        duckdb_threads=args.duckdb_threads,
        workers=args.workers,
    )

    print("\nDAILY EXIT CANDIDATE CONFIRMATION: COMPLETE", flush=True)
    print(f"  run fingerprint: {report['run_fingerprint']}", flush=True)
    print(
        f"  usable daily LONG cases: "
        f"{int(report['usable_daily_long_cases']):,}",
        flush=True,
    )
    print(
        "\n  STOP  TARGET    RETURN    MARKED_DD   BOOK_DD   TRADES   "
        "STOP/TARGET/TIME",
        flush=True,
    )
    for item in report["candidate_results"]:
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
        "\n  No candidate is automatically promoted from this result. "
        "Next we compare the unchanged candidates across earlier DEVELOPMENT "
        "regimes for robustness, then move to prospective SHADOW/PAPER gates.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
