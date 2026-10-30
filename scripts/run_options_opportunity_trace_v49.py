from __future__ import annotations

"""Offline complete decision trace for SPY 361-case V45/V46 and 106-case V47.

No new ThetaData requests, quote downloads, trades, strategy parameter search,
or hindsight admission. Use exact retained workstation report identities.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.simulation.options_opportunity_trace_v49 import build_trace
from packages.simulation.options_trace_journal_v49 import create_journal


def _load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not (0 < path.stat().st_size < 12*1024*1024):
        raise ValueError(f"V49_INPUT_MISSING_OVERSIZED_OR_SYMLINK:{path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v45", type=Path, required=True)
    parser.add_argument("--v46", type=Path, required=True)
    parser.add_argument("--v47", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V49 SPY FULL OPPORTUNITY TRACE + CLOCK/PRICE SENSITIVITY",flush=True)
    print("  OFFLINE source-only; zero provider/broker calls, no original gate changes",flush=True)
    try:
        journal = args.output.with_suffix(".jsonl")
        if (args.output.is_symlink() or args.output.exists()
                or journal.is_symlink() or journal.exists()):
            raise ValueError("V49_OUTPUT_OR_JOURNAL_EXISTS_OR_IS_SYMLINK")
        trace = build_trace(_load(args.v45), _load(args.v46), _load(args.v47))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        journal_report = create_journal(journal, trace)
        print(f"  journal={journal} audited_event_records={journal_report['total_records']}"
              f" hash_chain_tip={journal_report['final_record_sha256']}",flush=True)
        print(f"  original_decision_clocks={trace['original_weekly_decision_clocks']}"
              f" detailed_opportunity_traces={trace['traceable_original_selected_clocks']}"
              f" frozen_original_abstentions_without_source_case_ids=50",flush=True)
        print(f"  hypothetical_long_exit_dates={trace['hypothetical_long_exit_case_count']}"
              f" censored_skew_records={len(trace['censored_future_exit_skew_observations'])}"
              f" 1_to_3_second_skew_only_candidates={trace['censored_future_exit_skew_within_3s_only']}",flush=True)
        print("  Two-minute predecision-to-order price drift (NOT execution latency): "
              +repr(trace['two_minute_observed_price_change_band_descriptive_counts']),flush=True)
        print(f"  fingerprint={trace['fingerprint']} saved={args.output}",flush=True)
        print("  COMPLETE: ORIGINAL_1S_GATE_UNCHANGED NO_SIMULATED_LATENCY_QUOTES",flush=True)
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"  STOPPED: {type(exc).__name__}:{str(exc)[:250]}",flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
