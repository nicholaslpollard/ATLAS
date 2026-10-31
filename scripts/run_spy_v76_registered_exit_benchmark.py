from __future__ import annotations

"""V76 preregistered options-exit alternatives: source-cache-only quote shadow.

Original V55 entry, contract and source remain immutable. Full event journals
stored as signed JSON.gz. This runner NEVER issues provider calls or broker
orders. Retrospective training/development only, NOT held-out alpha.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.simulation.spy_v74_dynamic_sell_to_close_shadow import (
    replay, verified, signed, money, V74Error,
)
from scripts.run_spy_v74_original_dynamic_exit_cohort import signed_file
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ET=ZoneInfo("America/New_York")
ROOT=Path(__file__).resolve().parents[1]
CONTRACT="atlas-v76-preregistered-multi-exit-causal-quote-research-v1"
V69="atlas-v69-spy-source-first-multiwindow-exact-options-census-v1"
V65="atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"

# Freeze all research policy sets BEFORE observing any subsequent uninspected
# months. These are NOT trained, optimal or promising claims. Historical 2025
# January-June is already in-sample and may only illustrate them.
POLICIES={
    "v74_control":{"stop_loss_option_pct":"-50",
                  "take_profit_option_pct":"100",
                  "trailing_arm_pct":"20","trail_from_high_pct":"15",
                  "max_hold_minutes":180},
    "defensive_25_75":{"stop_loss_option_pct":"-25",
                      "take_profit_option_pct":"75",
                      "trailing_arm_pct":"10","trail_from_high_pct":"10",
                      "max_hold_minutes":120},
    "balanced_35_100":{"stop_loss_option_pct":"-35",
                      "take_profit_option_pct":"100",
                      "trailing_arm_pct":"20","trail_from_high_pct":"15",
                      "max_hold_minutes":120},
    "fast_25_40":{"stop_loss_option_pct":"-25",
                 "take_profit_option_pct":"40",
                 "trailing_arm_pct":"10","trail_from_high_pct":"10",
                 "max_hold_minutes":60},
    "runner_35_150":{"stop_loss_option_pct":"-35",
                    "take_profit_option_pct":"150",
                    "trailing_arm_pct":"30","trail_from_high_pct":"20",
                    "max_hold_minutes":180},
}
LAGS=(1,3)


def emit(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def store_gzip_once(path,doc):
    if not verified(doc):
        raise ValueError("V76_UNSIGNED_EVENT_DOCUMENT")
    if path.exists() or path.is_symlink():
        raise ValueError("V76_IMMUTABLE_JOURNAL_EXISTS")
    payload=(json.dumps(doc,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    with path.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream,mode="wb",compresslevel=7,
                           filename="",mtime=0) as gz:
            gz.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path,payload):
    doc=signed(payload)
    with path.open("x",encoding="utf8") as fh:
        json.dump(doc,fh,sort_keys=True,indent=2,allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return doc


def run(parent_dir,output_dir,*,expected_parent_sha,
        source_reader=_local_cache_only,settings_factory=load_settings,
        emit_event=emit):
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("V76_OUTPUT_ALREADY_EXISTS")
    if not expected_parent_sha or len(expected_parent_sha)!=64:
        raise ValueError("V76_EXACT_PARENT_SHA_REQUIRED")
    emit_event(f"STAGE_START V76 verify original signed V69 source chain path={parent_dir}")
    root=signed_file(parent_dir/"summary.json",V69,expected_parent_sha)
    if root["chunks"]!=1 or len(root["chunk_summaries"])!=1 or root["broker_orders"]!=0:
        raise ValueError("V76_ONE_SIGNED_MONTH_REQUIRED")
    chunk=signed_file(parent_dir/"chunk_0001.summary.json",V69,
                      root["chunk_summaries"][0]["fingerprint"])
    before=signed_file(parent_dir/"chunk_0001.preflight.json",V65,
                       chunk["original_v65_preflight_sha"])
    after=signed_file(parent_dir/"chunk_0001.replay.json",V65,
                      chunk["original_v65_post_source_sha"])
    receipts=signed_file(parent_dir/"chunk_0001.sources.json",V69)
    if (receipts["original_preflight_sha"]!=before["fingerprint"] or
        receipts["runtime_source_receipt"]!=chunk["source_resolution"] or
        after["broker_orders"]!=0 or after["provider_requests"]!=0):
        raise ValueError("V76_ORIGINAL_CHAIN_OR_AUTHORITY_MISMATCH")
    original={x["session"]:x for x in before["session_reports"]}
    days=after["session_reports"]
    if not days or len(original)!=len(days) or sorted(original)!=[x["session"] for x in days]:
        raise ValueError("V76_DAY_COVERAGE_OR_ORDER_MISMATCH")
    for row in days:
        first=original[row["session"]]
        if (not verified(row) or not verified(first) or
            row["signal_fingerprint"]!=first["signal_fingerprint"] or
            row["selected_contract"]!=first["selected_contract"] or
            row["exact_option_requirement"]!=first["exact_option_requirement"] or
            row["native_minute_source_sha256"]!=first["native_minute_source_sha256"]):
            raise ValueError("V76_ORIGINAL_ENTRY_OR_SOURCE_DRIFT")
    settings=settings_factory(ROOT,"development")
    emit_event(f"START V76 days={len(days)} policies={len(POLICIES)} "
               f"lags={len(LAGS)} original_options=READ_ONLY_SIGNED "
               "provider_calls=0 broker_orders=0")
    emit_event(f"STAGE_START V76 signed event journal writes directory={output_dir} "
               f"files_planned={len(days)*len(POLICIES)*len(LAGS)} "
               "compression=gzip output_immutable=True")
    output_dir.mkdir(parents=True,exist_ok=False)
    total=len(days)*len(POLICIES)*len(LAGS)
    completed=0
    progress_mark=10
    summaries=defaultdict(list)
    qcache={}
    for row in days:
        req=row.get("exact_option_requirement")
        receipt=row.get("exact_option_receipt")
        if (req is None)!=(receipt is None):
            raise ValueError("V76_SOURCE_REQUIREMENT_PAIR_INVALID")
        source=None
        if req is not None and receipt["state"]=="ARCHIVED":
            qid=receipt["query_id"]
            if qid not in qcache:
                emit_event(f"STAGE_START V76 original option SHA cache read "
                           f"date={row['session']} query={qid} provider_calls=0")
                x=source_reader(settings,qid)
                if x.get("cache_evidence")!="CACHE_HIT":
                    raise ValueError("V76_MISSING_OR_INVALID_ORIGINAL_SOURCE")
                qcache[qid]=x["source"]
            source=qcache[qid]
        for policy_name,params in POLICIES.items():
            for lag in LAGS:
                if req is not None and source is None:
                    entry=signed({
                        "contract":CONTRACT,"session":row["session"],
                        "parent_v65_sha":row["fingerprint"],
                        "status":"SOURCE_UNRESOLVED",
                        "reason":"EXPLICIT_SOURCE_NOT_ARCHIVED",
                        "source_state":receipt["state"],
                        "source_query_id":receipt["query_id"],
                        "policy":policy_name,"lag_seconds":lag,
                        "trade_net_pnl":None,"broker_orders":0,
                        "provider_calls":0,"events":[],
                    })
                else:
                    trial=replay(row,source,broker="webull",
                                 action_lag_seconds=lag,**params)
                    entry=signed({
                        "contract":CONTRACT,
                        "session":row["session"],
                        "parent_v65_sha":row["fingerprint"],
                        "policy":policy_name,
                        "policy_params":params,
                        "lag_seconds":lag,
                        "status":trial["status"],"reason":trial["reason"],
                        "trade_net_pnl":trial.get("trade_net_pnl"),
                        "original_source_sha256":receipt["archive_sha256"] if receipt else None,
                        "v74_inner_quote_shadow_report":trial,
                        "broker_orders":0,"provider_calls":0,
                        "historical_broker_fill_proven":False,
                        "experimental_in_sample":True,
                    })
                file_name=f"{row['session']}_{policy_name}_{lag}s.json.gz"
                zipped_sha=store_gzip_once(output_dir/file_name,entry)
                summaries[(policy_name,lag)].append({
                    "session":row["session"],"status":entry["status"],
                    "reason":entry["reason"],
                    "net_pnl":entry["trade_net_pnl"],
                    "original_row_fingerprint":row["fingerprint"],
                    "event_report_sha":entry["fingerprint"],
                    "stored_gzip_sha256":zipped_sha,
                    "stored_file":file_name,
                })
                completed+=1
                while progress_mark<=100 and completed*100>=total*progress_mark:
                    emit_event(f"PROGRESS_{progress_mark}PCT V76 "
                               f"completed={completed}/{total} "
                               f"date={row['session']} policy={policy_name} "
                               f"lag={lag}s status={entry['status']}")
                    progress_mark+=10
    policies=[]
    for policy_name in POLICIES:
        for lag in LAGS:
            rows=summaries[(policy_name,lag)]
            outcomes=[Decimal(d["net_pnl"]) for d in rows if d["net_pnl"] is not None]
            wins=sum(x for x in outcomes if x>0)
            losses=sum(x for x in outcomes if x<0)
            blocked=[r["session"] for r in rows
                     if r["status"] not in ("CLOSED_QUOTE_REFERENCE","NO_ENTRY","NO_SIGNAL")]
            policies.append({
                "name":policy_name,"lag_seconds":lag,
                "policy_params":POLICIES[policy_name],
                "closed_trade_count":len(outcomes),
                "win_count":sum(x>0 for x in outcomes),
                "loss_count":sum(x<0 for x in outcomes),
                "modeled_closed_trade_pnl":str(money(sum(outcomes))),
                "gross_profit_factor":str((wins/-losses).quantize(Decimal("0.0001"))) if losses else None,
                "unresolved_days":blocked,
                "entire_month_cash_valid":len(blocked)==0,
                "standalone_account_not_chained_across_months":True,
                "daily_event_receipts":rows,
            })
    report=write_once(output_dir/"summary.json",{
        "contract":CONTRACT,
        "original_v69_sha":root["fingerprint"],
        "source_month":[root["start"],root["end"]],
        "calendar_sessions":len(days),
        "policy_registry_fingerprint":signed({"policies":POLICIES})["fingerprint"],
        "policies":policies,
        "source_archive_count":len(qcache),
        "actual_historical_broker_option_fills":0,
        "provider_calls":0,"broker_orders":0,
        "out_of_sample_perf_proven":False,
        "cash_must_censor_at_first_unresolved_date":True,
        "this_month_outcomes_used_to_select_parameters":False,
    })
    emit_event(f"COMPLETE V76 days={len(days)} "
               f"variants={len(policies)} archive_cache_reads={len(qcache)} "
               f"output={output_dir/'summary.json'} "
               "provider_calls=0 broker_orders=0")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-v69-folder",type=Path,required=True)
    p.add_argument("--expected-v69-fingerprint",required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        run(a.parent_v69_folder,a.output_dir,
            expected_parent_sha=a.expected_v69_fingerprint)
        return 0
    except Exception as exc:
        emit(f"STOPPED V76 error_type={type(exc).__name__} "
             "broker_orders=0 provider_requests=0 "
             "original_archive_untouched=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
