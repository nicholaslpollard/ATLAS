from __future__ import annotations

"""V47 historical quote-reference fixed-hold diagnostic for V46 hypothetical LONGs.

This is not a PIT-eligible signal, broker execution or actual pilot performance.
Read-through V39/V38 acquires missing original call/put exit quotes automatically.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.simulation.spy_v47_counterfactual_quote_exit import (
    STRATEGY_VERSION, verified_cases, build_plan, exit_demands, report,
)
from packages.simulation.strategy_options_source_runtime_v39 import resolve_strategy_source_demands
from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor


def _load(path: Path, size_limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= size_limit:
        raise ValueError(f"V47_REQUIRED_REPORT_ABSENT_OR_OVERSIZED:{path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("V47_EXPECTED_JSON_OBJECT")
    return parsed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v46", type=Path, required=True)
    parser.add_argument("--v45", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V47 SPY 1-5 SESSION QUOTE EXIT ECONOMICS", flush=True)
    print("  V46=HYPOTHETICAL_SIGNALS ONLY fixed_holds=1..5 "
          "entry=10:01_ASK exit=FUTURE_10:01_BID "
          "source=READ_THROUGH_CACHED_OR_FETCHED", flush=True)
    try:
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("V47_OUTPUT_EXISTS")
        v46 = _load(args.v46, 8 * 1024 * 1024)
        v45 = _load(args.v45, 8 * 1024 * 1024)
        selected = verified_cases(v46, v45)
        plan = build_plan(selected)
        expected = len(plan) * 5 * 2
        observations: dict[str, dict] = {}

        def receive(item, source):
            day = item["candidate_id"].split(".")[2]
            observations.setdefault(day, {})[item["purpose"]] = (item, source)

        print(f"  hypothetical_long_dates={len(plan)} future_exit_source_uses={expected}",flush=True)
        print("  Historical quote receipt acquisition; each result cached under its exact source identity.",flush=True)
        with SourceProgressMonitor(expected_source_uses=expected) as progress:
            acquisition = resolve_strategy_source_demands(
                load_settings(ROOT, "development"), STRATEGY_VERSION, exit_demands(plan),
                on_source=receive, on_progress=progress.event, continue_on_error=True,
            )
        print("  Analyze 1-5-session paired quote exits; censor unqualified or missing receipts.",flush=True)
        result = report(v46, v45, plan, observations, acquisition)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        for hold, metrics in result["historical_quote_metrics_by_hold"].items():
            pm = metrics["primary_quote_reference_net_percent"]
            print(f"  hold={hold} quote_pairs={metrics['source_qualified_pairs']}/{metrics['requested_pairs']}"
                  f" censored={metrics['censored_pairs']}"
                  f" primary_mean_net_pct={pm['mean']} primary_median_net_pct={pm['median']}"
                  f" reference_profitable={pm['positive']}/{pm['n']}", flush=True)
        for row in result["chronological_one_slot_quote_reference_accounts"]:
            print(f"  account_hold={row['hold_sessions']} cost={row['cost_scenario']}"
                  f" modeled_closed={row['closed_quote_reference_pairs']}"
                  f" ending_cash_if_resolved={row['ending_cash_if_fully_resolved']}"
                  f" unresolved={row['unresolved_position'] is not None}", flush=True)
        print(f"  dispatches={acquisition['provider_dispatch_attempts']}"
              f" new_archives={acquisition['provider_fetch_successes']}"
              f" cache_hits={acquisition['persisted_cache_hits']}"
              f" errors={acquisition['source_uses_failed_or_unresolved']}",flush=True)
        print(f"  fingerprint={result['fingerprint']} saved={args.output}", flush=True)
        print("  COMPLETE: EXPLORATORY_QUOTE_REFERENCE_NOT_ACTUAL_STRATEGY_PROFITABILITY",flush=True)
        return 0 if acquisition["source_uses_failed_or_unresolved"] == 0 else 2
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}:{str(exc)[:350]}",flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
