from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.successor_orb_stocks_in_play_literature_v2_development import (
    MOVE_THRESHOLDS,
    run_orb_stocks_in_play_literature_v2_development,
)
from packages.strategies.successor_orb_stocks_in_play_literature_v2_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
)
from packages.strategies.successor_orb_stocks_in_play_literature_v2_development_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preregistered literature-fidelity 5-minute Stocks-in-Play ORB on "
            "DEVELOPMENT only. This is diagnostic research and cannot promote itself."
        )
    )
    parser.add_argument(
        "--authorize-development-orb-literature-v2",
        action="store_true",
        help=(
            "Required acknowledgement for DEVELOPMENT-only historical outcomes. No consumed "
            "master, future blind, provider, broker, PAPER/LIVE, promotion, confluence, or "
            "option-trading authority is granted."
        ),
    )
    return parser


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2%}"


def _mins(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}m"


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_orb_literature_v2:
        raise SystemExit(
            "Refusing ORB literature-v2 DEVELOPMENT outcomes without "
            "--authorize-development-orb-literature-v2"
        )

    print("ATLAS ORB Stocks-in-Play Literature v2 — DEVELOPMENT Diagnostic", flush=True)
    print(f"  strategy contract: {ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT}", flush=True)
    print(f"  analysis contract: {ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT}", flush=True)
    print(
        "  authority: DEVELOPMENT diagnostics only; master/future/provider/broker/PAPER/LIVE/"
        "promotion/confluence/option authority forbidden",
        flush=True,
    )

    report = run_orb_stocks_in_play_literature_v2_development(PROJECT_ROOT)
    counts = report["rank_counts"]
    totals = report["totals"]
    print("\nORB STOCKS-IN-PLAY LITERATURE V2: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(
        f"  opening snapshots / eligible rank pool / top20: "
        f"{int(counts['opening_snapshot_rows']):,} / {int(counts['eligible_rank_pool_rows']):,} / "
        f"{int(counts['selected_top20_rows']):,}",
        flush=True,
    )
    print(
        f"  directional / entered / comparable / same-minute unordered: "
        f"{int(totals['directional_candidates']):,} / {int(totals['entered']):,} / "
        f"{int(totals['comparable']):,} / {int(totals.get('same_minute_unordered', 0)):,}",
        flush=True,
    )
    print(
        f"  aggregate comparable: gross={_pct(totals.get('mean_gross_return'))} "
        f"primary(50bps)={_pct(totals.get('mean_primary_net_return'))} "
        f"stress(100bps)={_pct(totals.get('mean_stress_net_return'))} "
        f"MFE={_pct(totals.get('mean_path_mfe'))} MAE={_pct(totals.get('mean_path_adverse'))}",
        flush=True,
    )
    print("  direction diagnostics (descriptive; not a ranking):", flush=True)
    for row in report["direction_summary"]:
        print(
            f"    {row['direction']}: candidates={int(row['directional_candidates']):,} "
            f"comparable={int(row['comparable']):,} gross={_pct(row['mean_gross_return'])} "
            f"10/25/50/100={_pct(row['mean_net_return_10'])}/{_pct(row['mean_net_return_25'])}/"
            f"{_pct(row['mean_net_return_50'])}/{_pct(row['mean_net_return_100'])} "
            f"hold-med={_mins(row['median_holding_minutes'])} MFE={_pct(row['mean_path_mfe'])} "
            f"MAE={_pct(row['mean_path_adverse'])}",
            flush=True,
        )
    threshold_lookup = {
        (str(row["direction"]), float(row["move_threshold"])): row
        for row in report["threshold_summary"]
    }
    for direction in ("LONG", "SHORT"):
        available = [threshold_lookup.get((direction, threshold)) for threshold in MOVE_THRESHOLDS]
        available = [row for row in available if row is not None]
        if not available:
            continue
        print(f"  {direction} path timing:", flush=True)
        for row in available:
            print(
                f"    {int(round(float(row['move_threshold']) * 100))}%: "
                f"hit={_pct(row['favorable_hit_rate'])} "
                f"fav-first={_pct(row['favorable_before_adverse_rate'])} "
                f"adv-first={_pct(row['adverse_before_favorable_rate'])} "
                f"same-minute={_pct(row['same_minute_collision_rate'])} "
                f"med-fav={_mins(row['median_first_favorable_minutes'])}",
                flush=True,
            )
    print("  historical option P&L: not claimed", flush=True)
    print("  DEVELOPMENT self-validation / promotion / option-trading authority: false / false / false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
