from __future__ import annotations

"""Zero-provider V48 immutable V47 performance-evidence audit.

Analyses historical ASK-to-BID quote references for hypothetical V46
positions. Does not reselect, optimize or validate the original strategy.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.simulation.spy_v48_v47_evidence_audit import audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v47", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V48 FROZEN V47 NEGATIVE EVIDENCE AUDIT", flush=True)
    print("  ZERO_PROVIDER_CALLS ZERO_BROKER_CALLS NO_HINDSIGHT_SELECTION", flush=True)
    try:
        if args.v47.is_symlink() or not args.v47.is_file() or not 0 < args.v47.stat().st_size <= 12*1024*1024:
            raise ValueError("V48_INPUT_REPORT_MISSING_OR_OVERSIZED")
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("V48_OUTPUT_ALREADY_EXISTS")
        raw = json.loads(args.v47.read_text(encoding="utf-8"))
        result = audit(raw)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        print(f"  matched_quote_pairs={result['qualified_observed_pairs']}/530"
              f" censored={result['censored_pair_observations']}",flush=True)
        for h, costs in result["all_five_holds_by_cost_scenario"].items():
            p=costs["primary"]["conditional_quote_reference_returns_pct"]
            s=costs["stress"]["conditional_quote_reference_returns_pct"]
            print(f"  hold={h} n={p['sample']} win={p['positive']}"
                  f" mean_pct={p['mean_pct']} median_pct={p['median_pct']}"
                  f" mean_without_top_win_pct={p['mean_without_single_largest_winner_pct']}"
                  f" stressed_mean_pct={s['mean_pct']}",flush=True)
        for key,a in result["fully_resolved_original_one_day_cash_reference"].items():
            months=a["months_with_recorded_closures"]
            print(f"  ORIGINAL_ONE_DAY cost={key} ending_cash={a['ending_cash_quote_reference_only']}"
                  f" net_dollars={a['net_dollars']} wins={a['positive_pairs']}/48"
                  f" negative_active_months={months['negative']}/{months['active_windows']}",flush=True)
        print(f"  fingerprint={result['fingerprint']} saved={args.output}",flush=True)
        print("  COMPLETE: DEVELOPMENT_NEGATIVE_EXPLORATORY_EVIDENCE_NO_PROFITABILITY_CLAIM",flush=True)
        return 0
    except (ValueError, OSError, KeyError, TypeError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}:{str(exc)[:300]}",flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
