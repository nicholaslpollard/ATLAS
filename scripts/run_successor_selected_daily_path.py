from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.successor_selected_daily_path_analysis import (
    run_successor_selected_daily_path_analysis,
)
from packages.strategies.successor_selected_daily_path_contract import (
    MOVE_THRESHOLDS,
    SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure five-session favorable/adverse path timing for the already-selected "
            "successor DEVELOPMENT daily opportunities."
        )
    )
    parser.add_argument(
        "--authorize-development-selected-path",
        action="store_true",
        help=(
            "Required acknowledgement for post-result DEVELOPMENT-only path diagnostics. "
            "No consumed master, future blind, providers, brokers, PAPER/LIVE, promotion, "
            "confluence, or option-trading authority is granted."
        ),
    )
    return parser


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2%}"


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_selected_path:
        raise SystemExit(
            "Refusing selected daily path diagnostics without "
            "--authorize-development-selected-path"
        )
    print("ATLAS Successor Selected Daily Five-Session Path Diagnostics", flush=True)
    print(f"  contract fingerprint: {SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT}", flush=True)
    print(
        "  authority: selected DEVELOPMENT daily opportunities only; master/future/provider/"
        "broker/PAPER/LIVE/promotion/confluence/option authority forbidden",
        flush=True,
    )
    report = run_successor_selected_daily_path_analysis(PROJECT_ROOT)
    print("\nSUCCESSOR SELECTED DAILY PATH: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(f"  selected daily comparable: {int(report['selected_daily_comparable']):,}", flush=True)
    print("  horizon: next-open through five trading sessions", flush=True)
    print("  threshold first-touch resolution: session-level; same-day both-side touches remain unordered", flush=True)

    thresholds = {
        (row["policy_id"], row["direction"], float(row["move_threshold"])): row
        for row in report["route_threshold_summary"]
    }
    print("  route diagnostics (descriptive; policy-id order, not ranking):", flush=True)
    for route in report["route_path_summary"]:
        key = (route["policy_id"], route["direction"])
        chunks: list[str] = []
        for threshold in MOVE_THRESHOLDS:
            row = thresholds[(key[0], key[1], float(threshold))]
            chunks.append(
                f"{int(round(threshold * 100))}% hit={_pct(row['favorable_hit_rate_5'])} "
                f"fav-first={_pct(row['favorable_before_adverse_rate'])}"
            )
        print(
            f"    {key[0]} {key[1]}: n={int(route['selected_comparable']):,} "
            f"close5={_pct(route['mean_gross_return_5'])} MFE5={_pct(route['mean_mfe_5'])} "
            f"MAE5={_pct(route['mean_adverse_excursion_5'])} "
            f"capture={_pct(route['mean_exit_capture_ratio'])} giveback={_pct(route['mean_peak_giveback'])}; "
            + " | ".join(chunks),
            flush=True,
        )
    print("  intraday routes: deferred to separate minute-path diagnostic", flush=True)
    print("  historical option P&L: not claimed", flush=True)
    print("  strategy promotion / option-trading authority: false / false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
