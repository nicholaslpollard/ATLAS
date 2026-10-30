from __future__ import annotations

"""First paid-source CANARY for one exact historical SPY 0DTE call/put.

Makes at most one V38 exact history read-through request; cache hit uses no
provider. The selected strike/time are diagnostic only and NOT an ORB trade.
"""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__" and not __package__:
    sys.path.insert(0,str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_on_demand_source_cache_v38 import read_through_historical_options
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-spy-0dte-first-intraday-exact-quote-source-canary-v52"
DEFAULT_DATE="2025-06-09"
DEFAULT_STRIKE="604"
MAX_PREVIEW_ROWS=3


def summarize_source(source: dict, *, strike: str, right: str, session: str) -> dict:
    rows=source["source_rows"]
    sample=[]
    present_keys=set()
    timestamps=[]
    identity_mismatches=[]
    # Restrict *display* to schema and bounded numeric/timestamp fields.
    for idx,row in enumerate(rows):
        present_keys.update(row.keys())
        for key in ("timestamp","timestamp_et","datetime","date","ms_of_day","timestamp_utc"):
            if key in row and len(timestamps)<5:
                timestamps.append({"row":idx,"field":key,"value":str(row[key])[:100]})
        for name,expected in (("symbol","SPY"),("expiration",session),("right",right)):
            if name in row and row[name] is not None and str(row[name])!=expected:
                identity_mismatches.append({"row":idx,"field":name,"observed":str(row[name])[:80]})
        if "strike" in row and row["strike"] is not None:
            try:
                if abs(float(row["strike"])-float(strike))>0.000001:
                    identity_mismatches.append({"row":idx,"field":"strike","observed":str(row["strike"])[:80]})
            except (TypeError,ValueError):
                identity_mismatches.append({"row":idx,"field":"strike","observed":"NON_NUMERIC"})
        if idx<MAX_PREVIEW_ROWS:
            sample.append({
                "row_index":idx,
                "fields":{k:row[k] for k in (
                    "timestamp","timestamp_et","ms_of_day","bid","ask",
                    "bid_size","ask_size","bid_condition","ask_condition"
                ) if k in row},
            })
    fingerprinted={
        "contract":CONTRACT,"mode":"EXACT_CONTRACT_SOURCE_SCHEMA_CANARY_NO_TRADES",
        "session_date":session,"requested_expiration":session,
        "requested_strike":strike,"requested_right":right,
        "request_identity":source["exact_requirement"],
        "source_status":source["status"],
        "source_query_id":source["query_id"],
        "source_sha256":source["source_sha256"],
        "rows":len(rows),
        "source_row_field_names":sorted(present_keys),
        "first_observed_timestamp_field_samples":timestamps,
        "preview_first_three_rows":sample,
        "contract_identity_conflicts":identity_mismatches[:20],
        "contract_identity_conflict_count":len(identity_mismatches),
        "per_row_contract_identity_provable":all(
            k in present_keys for k in ("symbol","expiration","strike","right")),
        "timestamp_column_present":any(
            k in present_keys for k in ("timestamp","timestamp_et","datetime","ms_of_day","timestamp_utc")),
        "independent_historical_publication_verified":False,
        "historical_fill_verified":False,
        "historical_strategy_pnl":None,
        "provider_requests_at_most_one":True,
    }
    fingerprinted["fingerprint"]=_fingerprint(fingerprinted)
    return fingerprinted


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",default=DEFAULT_DATE)
    parser.add_argument("--strike",default=DEFAULT_STRIKE)
    parser.add_argument("--right",choices=("call","put"),default="call")
    parser.add_argument("--interval",choices=("1s","tick","1m"),default="1s")
    parser.add_argument("--start",default="09:35:00.000")
    parser.add_argument("--end",default="09:37:00.000")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    print("ATLAS V52 SPY EXACT CONTRACT INTRADAY SOURCE CANARY",flush=True)
    print("  one session, one expiration, one strike, one option right, bounded minutes",flush=True)
    print("  REAL historical provider call only on cache MISS, NO BROKER",flush=True)
    try:
        date.fromisoformat(args.date)
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("V52_SOURCE_CANARY_OUTPUT_MUST_BE_NEW")
        settings=load_settings(ROOT,"development")
        query={
            "symbol":"SPY","date_et":args.date,"expiration":args.date,
            "strike":args.strike,"right":args.right,
            "start_time_et":args.start,"end_time_et":args.end,
            "interval":args.interval,
        }
        src=read_through_historical_options(
            settings,"option_history_exact_quote_tape",query)
        summary=summarize_source(src,strike=args.strike,right=args.right,session=args.date)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as f:
            json.dump(summary,f,indent=2,sort_keys=True,default=str)
            f.write("\n")
        print(f"  source_status={summary['source_status']} rows={summary['rows']}"
              f" fields={summary['source_row_field_names']}",flush=True)
        print(f"  source_identity_conflicts={summary['contract_identity_conflict_count']}"
              f" independent_publication_proven=False historical_fills=0",flush=True)
        print(f"  exact_cache_query_id={summary['source_query_id']}",flush=True)
        print(f"  preview_saved={args.output} original_source_sha={summary['source_sha256']}",flush=True)
        print("  COMPLETE: DIAGNOSTIC_ORIGINAL_QUOTES_NOT_ORB_TRADES",flush=True)
        return 0 if not summary["contract_identity_conflict_count"] and summary["rows"] else 2
    except Exception as exc:
        # Do not echo raw provider exceptions, which may include secrets.
        print(f"  STOPPED: {type(exc).__name__}; see ATLAS provider logs only if sanitized",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
