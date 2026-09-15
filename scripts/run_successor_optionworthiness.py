from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.successor_optionworthiness_analysis import (
    run_successor_optionworthiness_analysis,
)
from packages.strategies.successor_optionworthiness_contract import (
    SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Derive descriptive underlying move-magnitude, excursion, available holding-time, "
            "walk-forward stability, and strategy-inventory diagnostics from the exact accepted "
            "successor DEVELOPMENT conditioning artifacts."
        )
    )
    parser.add_argument(
        "--authorize-development-optionworthiness",
        action="store_true",
        help=(
            "Required acknowledgement that this opens additional post-result DEVELOPMENT-only "
            "diagnostic aggregates from already accepted retained artifacts. It does not read raw "
            "market data, option history, consumed master, future blind, providers, brokers, or "
            "grant PAPER/LIVE/promotion/confluence/option-trading authority."
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_development_optionworthiness:
        raise SystemExit(
            "Refusing to open successor option-worthiness diagnostics without "
            "--authorize-development-optionworthiness"
        )
    print("ATLAS Successor DEVELOPMENT Option-Worthiness Diagnostics", flush=True)
    print(f"  option-worthiness fingerprint: {SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT}", flush=True)
    print(
        "  authority: retained DEVELOPMENT conditioning artifacts only; raw market/options/master/"
        "future/provider/broker/PAPER/LIVE/promotion/confluence forbidden",
        flush=True,
    )
    report = run_successor_optionworthiness_analysis(PROJECT_ROOT)
    counts = report["scope_counts"]
    inventory = report["strategy_inventory"]
    print("\nSUCCESSOR OPTION-WORTHINESS: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(
        "  comparable all / walk-forward test / selected: "
        f"{int(counts['development_all_comparable']):,} / "
        f"{int(counts['walk_forward_test_comparable']):,} / "
        f"{int(counts['walk_forward_selected_comparable']):,}",
        flush=True,
    )
    print(
        f"  strategy inventory: {int(inventory['policy_routes'])} routes / "
        f"{int(inventory['economic_families'])} economic families",
        flush=True,
    )
    print("  exact time-to-threshold: unavailable from retained artifacts; not claimed", flush=True)
    print("  ATR-normalized threshold frequency: unavailable from retained artifacts; not claimed", flush=True)
    print("  historical option P&L: unavailable; not claimed", flush=True)
    print("  confluence opened: false", flush=True)
    print("  promotion / option-trading authority: false / false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
