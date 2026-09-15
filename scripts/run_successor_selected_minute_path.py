from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.successor_selected_minute_path_analysis import (
    run_successor_selected_minute_path_analysis,
)
from packages.strategies.successor_selected_daily_path_contract import MOVE_THRESHOLDS
from packages.strategies.successor_selected_minute_path_contract import (
    SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure exact minute-resolution favorable/adverse first-touch timing for the "
            "already-selected successor DEVELOPMENT intraday opportunities."
        )
    )
    parser.add_argument(
        "--authorize-development-selected-minute-path",
        action="store_true",
        help=(
            "Required acknowledgement for post-result DEVELOPMENT-only minute path diagnostics. "
            "No consumed master, future blind, provider, broker, PAPER/LIVE, promotion, "
            "confluence, or option-trading authority is granted."
        ),
    )
    return parser


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2%}"


def _mins(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}m"


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_selected_minute_path:
        raise SystemExit(
            "Refusing selected minute path diagnostics without "
            "--authorize-development-selected-minute-path"
        )
    print("ATLAS Successor Selected Minute Path Diagnostics", flush=True)
    print(f"  contract fingerprint: {SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT}", flush=True)
    print(
        "  authority: selected DEVELOPMENT minute opportunities only; master/future/provider/"
        "broker/PAPER/LIVE/promotion/confluence/option authority forbidden",
        flush=True,
    )
    report = run_successor_selected_minute_path_analysis(PROJECT_ROOT)
    print("\nSUCCESSOR SELECTED MINUTE PATH: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(f"  selected minute comparable: {int(report['selected_minute_comparable']):,}", flush=True)
    print(
        f"  selected symbols / verified native units / raw path bars: "
        f"{int(report['selected_symbol_count']):,} / "
        f"{int(report['verified_native_unit_count']):,} / "
        f"{int(report['raw_path_bar_count']):,}",
        flush=True,
    )
    print(
        "  first-touch resolution: exact minute-bar timestamp; same-minute both-side touches "
        "remain unordered; exit-bar high/low extremes are excluded",
        flush=True,
    )

    thresholds = {
        (row["policy_id"], row["direction"], float(row["move_threshold"])): row
        for row in report["route_threshold_summary"]
    }
    print("  route diagnostics (descriptive; policy/direction order, not a ranking):", flush=True)
    for route in report["route_path_summary"]:
        key = (route["policy_id"], route["direction"])
        chunks: list[str] = []
        for threshold in MOVE_THRESHOLDS:
            row = thresholds[(key[0], key[1], float(threshold))]
            chunks.append(
                f"{int(round(threshold * 100))}% hit={_pct(row['favorable_hit_rate'])} "
                f"fav-first={_pct(row['favorable_before_adverse_rate'])} "
                f"med-t={_mins(row['median_first_favorable_minutes'])}"
            )
        print(
            f"    {key[0]} {key[1]}: n={int(route['selected_comparable']):,} "
            f"gross={_pct(route['mean_gross_return'])} primary={_pct(route['mean_primary_net_return'])} "
            f"stress={_pct(route['mean_stress_net_return'])} "
            f"hold-med={_mins(route['median_holding_minutes'])} "
            f"MFE={_pct(route['mean_path_mfe'])} MAE={_pct(route['mean_path_adverse'])}; "
            + " | ".join(chunks),
            flush=True,
        )
    print("  historical option P&L: not claimed", flush=True)
    print("  strategy promotion / option-trading authority: false / false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
