from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.recurrent_successor_dynamic_exit_v1 import (
    run_recurrent_successor_dynamic_exit_v1,
)
from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    DYNAMIC_EXIT_ACTIONS,
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
    SOURCE_STATIC_REGIME_RUN_FINGERPRINT,
    dynamic_exit_action_id,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Dynamic Exit V1 walk-forward selector diagnostics over "
            "DEVELOPMENT daily LONG cases."
        )
    )
    parser.add_argument(
        "--authorize-development-dynamic-exit",
        action="store_true",
        help=(
            "Required acknowledgement that this is DEVELOPMENT research only "
            "and grants no PAPER/LIVE/promotion authority."
        ),
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
    if not args.authorize_development_dynamic_exit:
        raise SystemExit(
            "Refusing to run Dynamic Exit V1 without "
            "--authorize-development-dynamic-exit"
        )

    print("ATLAS Recurrent Successor Dynamic Exit V1", flush=True)
    print(
        "  contract fingerprint: "
        + RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
        flush=True,
    )
    print(
        "  source static-regime fingerprint: "
        + SOURCE_STATIC_REGIME_RUN_FINGERPRINT,
        flush=True,
    )
    print(
        "  frozen actions: "
        + ", ".join(
            dynamic_exit_action_id(stop, target)
            for stop, target in DYNAMIC_EXIT_ACTIONS
        )
        + ", ABSTAIN",
        flush=True,
    )
    print(
        "  selection: prior completed folds only; current future path forbidden",
        flush=True,
    )
    print(
        "  authority: DEVELOPMENT selector diagnostic only; "
        "no portfolio return/promotion/PAPER/LIVE authority",
        flush=True,
    )

    report = run_recurrent_successor_dynamic_exit_v1(
        PROJECT_ROOT,
        policy_ids=tuple(args.policy_id),
        output_root=args.output_root,
        duckdb_threads=args.duckdb_threads,
    )

    print("\nDYNAMIC EXIT V1 SELECTOR: COMPLETE", flush=True)
    print(f"  run fingerprint: {report['run_fingerprint']}", flush=True)
    print(f"  usable cases: {int(report['usable_cases']):,}", flush=True)
    print(f"  selected: {int(report['selected_cases']):,}", flush=True)
    print(f"  abstained: {int(report['abstained_cases']):,}", flush=True)
    print(f"  selection rate: {float(report['selection_rate']):.2%}", flush=True)

    diagnostics = dict(report["selected_realized_trade_diagnostics"])
    mean_net = diagnostics.get("mean_net_return")
    median_net = diagnostics.get("median_net_return")
    probability_positive = diagnostics.get("probability_positive")
    print(
        "  selected realized trade diagnostic: "
        f"mean={'n/a' if mean_net is None else format(float(mean_net), '.3%')}; "
        f"median={'n/a' if median_net is None else format(float(median_net), '.3%')}; "
        f"P(positive)="
        f"{'n/a' if probability_positive is None else format(float(probability_positive), '.2%')}",
        flush=True,
    )

    print("\n  Action counts:", flush=True)
    for action_id, count in report["selected_action_counts"].items():
        print(f"    {action_id}: {int(count):,}", flush=True)

    print("\n  Annual selector diagnostics:", flush=True)
    print(
        "  YEAR   CASES   SELECTED   RATE      MEAN_NET   P(POSITIVE)",
        flush=True,
    )
    for item in report["year_summary"]:
        mean_value = item["mean_selected_realized_net_return"]
        positive_value = item["probability_positive_selected_realized"]
        print(
            f"  {int(item['year'])}  "
            f"{int(item['cases']):>6,}  "
            f"{int(item['selected']):>8,}  "
            f"{float(item['selection_rate']):>7.2%}  "
            f"{'n/a' if mean_value is None else format(float(mean_value), '.3%'):>10}  "
            f"{'n/a' if positive_value is None else format(float(positive_value), '.2%'):>11}",
            flush=True,
        )

    print(
        "\n  IMPORTANT: these are per-trade selector diagnostics, not account "
        "returns. Capital competition, portfolio caps and compounding are "
        "deliberately deferred until the selector passes this gate.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
