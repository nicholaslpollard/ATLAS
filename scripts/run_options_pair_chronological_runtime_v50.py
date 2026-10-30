from __future__ import annotations

"""V50 offline, source-supplied chronological options pair quote-reference simulator.

The input's causal eligibility must be independently supported by the caller;
this tool does NOT promote V46 assumption-only signals to historical trades.
No provider/broker reads, order routing, or claim of executable fills.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__" and not __package__:
    sys.path.insert(0,str(ROOT))

from packages.simulation.options_opportunity_trace_v49 import fingerprint
from packages.simulation.options_pair_chronological_runtime_v50 import replay_pairs
from packages.simulation.options_pair_runtime_journal_v50 import save_runtime_journal


def _read_cases(path: Path) -> tuple[list[dict],str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size>128*1024*1024:
        raise ValueError("V50_INPUT_FILE_INVALID_OR_TOO_LARGE")
    raw=path.read_bytes()
    packet=json.loads(raw.decode("utf-8"))
    if not isinstance(packet,dict) or not isinstance(packet.get("cases"),list):
        raise ValueError("V50_EXPECTED_INPUT_OBJECT_WITH_CASES")
    return packet["cases"],hashlib.sha256(raw).hexdigest()


def main(argv=None) -> int:
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cases",type=Path,required=True)
    cli.add_argument("--output",type=Path,required=True)
    cli.add_argument("--skew-seconds",type=int,choices=(1,3),default=1)
    cli.add_argument("--adverse-action-drift-pct",choices=("0.5","1","2"),default="1")
    cli.add_argument("--starting-cash",default="100000.00")
    cli.add_argument("--risk-fraction",default="0.05")
    cli.add_argument("--profit-target-pct",default="20")
    cli.add_argument("--stop-loss-pct",default="-10")
    cli.add_argument("--maximum-hold-reviews",type=int,default=5)
    args=cli.parse_args(argv)
    print("ATLAS V50 CHRONOLOGICAL OPTIONS-PAIR REFERENCE SIMULATOR",flush=True)
    print("  OFFLINE; no provider/broker calls; action-time quotes required; NOT historical fills",flush=True)
    try:
        journal=args.output.with_suffix(".jsonl")
        if (args.output.exists() or args.output.is_symlink()
                or journal.exists() or journal.is_symlink()):
            raise ValueError("V50_OUTPUT_OR_JOURNAL_ALREADY_EXISTS")
        cases,input_sha=_read_cases(args.cases)
        replay=replay_pairs(
            cases,starting_cash=args.starting_cash,
            cash_risk_fraction=args.risk_fraction,
            profit_target_pct=args.profit_target_pct,
            stop_loss_pct=args.stop_loss_pct,
            maximum_hold_reviews=args.maximum_hold_reviews,
            pair_skew_seconds=args.skew_seconds,
            maximum_adverse_action_drift_pct=args.adverse_action_drift_pct,
        )
        replay["input_case_file_sha256"]=input_sha
        replay["fingerprint"]=fingerprint({k:v for k,v in replay.items() if k!="fingerprint"})
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as f:
            json.dump(replay,f,sort_keys=True,indent=2,allow_nan=False)
            f.write("\n")
        audit=save_runtime_journal(journal,replay)
        print(f"  cases={replay['opportunities_evaluated']} entry_reference_count={replay['modeled_quote_reference_entries']}"
              f" exit_reference_count={replay['modeled_quote_reference_exits']}"
              f" unresolved={replay['open_unresolved_position_id']}",flush=True)
        print(f"  abstention and entry reasons={replay['opportunity_dispositions']}",flush=True)
        print(f"  account_equity_if_resolved={replay['terminal_equity_if_fully_resolved']}",flush=True)
        print(f"  saved_report={args.output} source_sha256={input_sha}",flush=True)
        print(f"  verified_journal={journal} records={audit['total_journal_records']}"
              f" tip_sha256={audit['final_record_sha256']}",flush=True)
        print("  COMPLETE: NO_BROKER_FILLS_NO_VERIFIED_STRATEGY_PROFITABILITY",flush=True)
        return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(f"  STOPPED: {type(exc).__name__}:{str(exc)[:250]}",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
