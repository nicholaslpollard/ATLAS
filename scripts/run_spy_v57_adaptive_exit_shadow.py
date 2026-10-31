from __future__ import annotations

"""Reevaluate already archived V55/V56 quote evidence under V57 adaptive exits.

OFFLINE only: zero provider requests and zero broker orders. Input is the
original immutable JSON report plus independently verified SHA-chained JSONL.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.simulation.spy_v55_event_journal import verify_journal
from packages.simulation.spy_v57_causal_exit_shadow import replay_adaptive_shadow


def log(message):
    stamp=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{stamp}] {message}",flush=True)


def execute(input_path,output_path):
    log(f"START V57 causal_adaptive_exit_shadow input={input_path}"
        " original_provider_calls=0 broker_orders=0")
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("V57_OUTPUT_ALREADY_EXISTS")
    journal=input_path.with_suffix(".jsonl")
    log(f"STAGE_START verify_original_hash_chained_journal path={journal}")
    original_proof=verify_journal(journal)
    log(f"STAGE_PASS original_journal rows={original_proof['journal_rows']}"
        f" tip={original_proof['tip_sha256']}")
    log(f"STAGE_START read_original_event_report path={input_path}")
    with input_path.open("r",encoding="utf-8") as handle:
        original=json.load(handle)
    if original_proof["report_fingerprint"]!=original.get("fingerprint"):
        raise ValueError("V57_PARENT_REPORT_AND_HASH_JOURNAL_DISAGREE")
    log(f"STAGE_PASS original_report verified_events={len(original.get('events',[]))}")
    log("STAGE_START replay_prior_only_adaptive_exit_rules"
        " risk_budget=0.5pct_of_equity"
        " high_water_trail=10-20pct cutoff=15:00")
    report=replay_adaptive_shadow(original)
    log(f"STAGE_PASS adaptive_exit_eval"
        f" status={report['status']} observations={report['observed_quotes']}"
        f" original_net={original.get('trade_net_pnl')}"
        f" experimental_net={report['net_pnl']}"
        " no_guaranteed_fills=True")
    log(f"STAGE_START persist_immutable_full_adaptive_quote_decision_audit path={output_path}")
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open("x",encoding="utf-8") as handle:
        json.dump(report,handle,sort_keys=True,indent=2,allow_nan=False)
        handle.write("\n")
    log(f"COMPLETE V57"
        f" saved={output_path} report_fingerprint={report['fingerprint']}"
        f" status={report['status']} parent_net={original.get('trade_net_pnl')}"
        f" adaptive_net={report['net_pnl']}"
        " paid_requests=0 broker_orders=0 profitability_claimed=False")
    return 0 if report["status"] in ("NO_ENTRY_IN_PARENT","CLOSED_ADAPTIVE_QUOTE_REFERENCE") else 2


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        return execute(args.input,args.output)
    except Exception as exc:
        log(f"STOPPED V57 error_type={type(exc).__name__}"
            " source_remains_unchanged=True no_provider_calls=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
