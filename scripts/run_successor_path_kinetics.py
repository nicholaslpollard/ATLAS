from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.successor_path_kinetics_analysis import (
    run_successor_path_kinetics_analysis,
)
from packages.strategies.successor_path_kinetics_contract import (
    SUCCESSOR_PATH_KINETICS_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure day-resolution move timing and favorable/adverse path kinetics for exactly the "
            "already-selected comparable daily successor DEVELOPMENT opportunities."
        )
    )
    parser.add_argument(
        "--authorize-development-path-kinetics",
        action="store_true",
        help=(
            "Required acknowledgement that this rereads only the hash-bound DEVELOPMENT daily view "
            "for already-selected comparable daily opportunities. It does not read the consumed "
            "master, future blind, providers, brokers, option history, or grant PAPER/LIVE/"
            "promotion/confluence/option-trading authority."
        ),
    )
    return parser


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2%}"


def _day(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}d"


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_path_kinetics:
        raise SystemExit(
            "Refusing to open successor path kinetics without "
            "--authorize-development-path-kinetics"
        )
    print("ATLAS Successor DEVELOPMENT Daily Path-Kinetics Diagnostics", flush=True)
    print(f"  path-kinetics fingerprint: {SUCCESSOR_PATH_KINETICS_FINGERPRINT}", flush=True)
    print(
        "  authority: selected comparable daily DEVELOPMENT opportunities only; hash-bound daily "
        "source reread; master/future/provider/broker/options/PAPER/LIVE/promotion/confluence forbidden",
        flush=True,
    )
    report = run_successor_path_kinetics_analysis(PROJECT_ROOT)
    counts = report["scope_counts"]
    print("\nSUCCESSOR DAILY PATH KINETICS: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(
        "  selected comparable total / daily analyzed / intraday retained-not-reopened: "
        f"{int(counts['selected_comparable_total']):,} / "
        f"{int(counts['selected_daily_comparable_analyzed']):,} / "
        f"{int(counts['selected_intraday_comparable_not_reopened']):,}",
        flush=True,
    )
    print("  five-session move timing by selected daily route (descriptive; no ranking score):", flush=True)
    for row in report.get("five_session_route_diagnostics") or []:
        print(
            f"    {row['policy_id']} {row['direction']}: n={int(row['selected_comparable']):,} "
            f"primary={_pct(row.get('mean_primary_net_return'))} stress={_pct(row.get('mean_stress_net_return'))} "
            f"P(+2/+3/+5% by5)={_pct(row.get('p_favorable_2pct_by_5'))}/"
            f"{_pct(row.get('p_favorable_3pct_by_5'))}/{_pct(row.get('p_favorable_5pct_by_5'))} "
            f"P(-2% adverse by5)={_pct(row.get('p_adverse_2pct_by_5'))} "
            f"median +2% hit={_day(row.get('median_first_favorable_2pct_session'))} "
            f"same-day 2% ambiguity={_pct(row.get('p_same_session_ambiguous_2pct_by_5'))}",
            flush=True,
        )
    print("  thresholds: 1% / 2% / 3% / 5%", flush=True)
    print("  horizons: 1 / 2 / 3 / 5 / 10 / 20 trading sessions", flush=True)
    print("  entry: next regular-session open after the signal session", flush=True)
    print("  same daily bar favorable/adverse ordering: ambiguous; never inferred", flush=True)
    print("  historical option P&L: unavailable; not claimed", flush=True)
    print("  confluence opened: false", flush=True)
    print("  promotion / option-trading authority: false / false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
