from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.recurrent_successor_daily_exit_regime_robustness import (
    run_recurrent_successor_daily_exit_regime_robustness,
)
from packages.backtesting.recurrent_successor_daily_exit_regime_robustness_contract import (
    ANNUAL_REGIME_WINDOWS,
    RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT,
    SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT,
)
from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    CANDIDATE_EXIT_POLICIES,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run unchanged 2%/5% and 3%/5% daily exit candidates across "
            "annual 2018-2024 DEVELOPMENT regimes."
        )
    )
    parser.add_argument(
        "--authorize-development-regime-robustness",
        action="store_true",
        help=(
            "Required acknowledgement that this is retrospective DEVELOPMENT "
            "robustness only and grants no PAPER/LIVE/promotion authority."
        ),
    )
    parser.add_argument(
        "--initial-equity",
        type=float,
        required=True,
        help="Starting simulation equity for each annual regime.",
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
        help="Optional regime-policy process worker count.",
    )
    parser.add_argument(
        "--duckdb-threads",
        type=int,
        default=None,
        help="Optional DuckDB thread count for the one-time source load.",
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
    if not args.authorize_development_regime_robustness:
        raise SystemExit(
            "Refusing to run retrospective DEVELOPMENT regime robustness without "
            "--authorize-development-regime-robustness"
        )

    print("ATLAS Recurrent Daily Exit Regime Robustness", flush=True)
    print(
        "  contract fingerprint: "
        + RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT,
        flush=True,
    )
    print(
        "  source 2026 confirmation fingerprint: "
        + SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT,
        flush=True,
    )
    print(
        "  unchanged candidates: "
        + ", ".join(
            f"STOP {stop:.0%} / TARGET {target:.0%}"
            for stop, target in CANDIDATE_EXIT_POLICIES
        ),
        flush=True,
    )
    print(
        "  annual regimes: "
        + ", ".join(regime_id for regime_id, _, _ in ANNUAL_REGIME_WINDOWS),
        flush=True,
    )
    print(
        f"  equity reset: ${args.initial_equity:,.2f} at the start of each regime",
        flush=True,
    )
    print(
        "  authority: retrospective DEVELOPMENT robustness only; "
        "no promotion/PAPER/LIVE authority",
        flush=True,
    )

    report = run_recurrent_successor_daily_exit_regime_robustness(
        PROJECT_ROOT,
        initial_equity=args.initial_equity,
        policy_ids=tuple(args.policy_id),
        output_root=args.output_root,
        duckdb_threads=args.duckdb_threads,
        workers=args.workers,
    )

    print("\nDAILY EXIT REGIME ROBUSTNESS: COMPLETE", flush=True)
    print(f"  run fingerprint: {report['run_fingerprint']}", flush=True)
    print(
        f"  total loaded usable cases: "
        f"{int(report['total_loaded_usable_cases']):,}",
        flush=True,
    )

    print(
        "\n  YEAR  STOP  TARGET    RETURN    MARKED_DD   BOOK_DD   "
        "TRADES   STOP/TARGET/TIME",
        flush=True,
    )
    for item in report["regime_results"]:
        if item["status"] != "COMPLETE":
            print(
                f"  {item['regime_id']}  "
                f"{float(item['stop_fraction']):>4.0%}  "
                f"{float(item['target_fraction']):>6.0%}  "
                "NO_USABLE_CASES",
                flush=True,
            )
            continue
        exits = dict(item.get("exit_dispositions") or {})
        print(
            f"  {item['regime_id']}  "
            f"{float(item['stop_fraction']):>4.0%}  "
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

    print("\n  Cross-regime summary:", flush=True)
    for item in report["candidate_summary"]:
        median_return = item["median_regime_return"]
        worst_return = item["worst_regime_return"]
        worst_dd = item["worst_marked_drawdown"]
        print(
            f"  STOP {float(item['stop_fraction']):.0%} / "
            f"TARGET {float(item['target_fraction']):.0%}: "
            f"positive={int(item['positive_regimes'])}/"
            f"{int(item['regimes_with_usable_cases'])}; "
            f"median return="
            f"{'n/a' if median_return is None else format(float(median_return), '.2%')}; "
            f"worst return="
            f"{'n/a' if worst_return is None else format(float(worst_return), '.2%')}; "
            f"worst marked DD="
            f"{'n/a' if worst_dd is None else format(float(worst_dd), '.2%')}",
            flush=True,
        )

    print(
        "\n  These are retrospective robustness diagnostics. "
        "They characterize when static exits work or fail; they do not rescue "
        "the failed 2026 forward confirmation or promote either candidate.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
