from __future__ import annotations

"""V74: offline two-broker-policy dynamic option exits from signed original V69/V73.

All entry decisions remain frozen; source archives are read SHA-verified with
SQLite mode=ro. Does not create/retry provider requests or broker orders.
"""

import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v74_dynamic_sell_to_close_shadow import (
    CONTRACT, BROKERS, V74Error, replay, signed, verified,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
V69="atlas-v69-spy-source-first-multiwindow-exact-options-census-v1"
V65="atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"


def event(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def signed_file(path,expected_contract,expected_hash=None):
    if path.is_symlink() or not path.is_file():
        raise V74Error("V74_SOURCE_REPORT_MISSING_OR_LINKED")
    doc=json.loads(path.read_text(encoding="utf8"))
    if (not verified(doc) or doc.get("contract")!=expected_contract
            or expected_hash is not None and doc["fingerprint"]!=expected_hash):
        raise V74Error("V74_SOURCE_REPORT_SIGNATURE_OR_IDENTITY_INVALID")
    return doc


def write_once(path,doc):
    result=signed(doc)
    with path.open("x",encoding="utf8") as fh:
        json.dump(result,fh,sort_keys=True,indent=2,allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return result


def review(v69_folder,output_dir,*,expected_fingerprint,
           action_lag_seconds=1,
           settings_factory=load_settings,source_reader=_local_cache_only,
           emit=event):
    if action_lag_seconds not in (1,3):
        raise V74Error("V74_EXIT_ACTION_LAG_INVALID")
    if output_dir.exists() or output_dir.is_symlink():
        raise V74Error("V74_IMMUTABLE_OUTPUT_EXISTS")
    emit(f"STAGE_START V74 verify_signed_parent folder={v69_folder} "
         "no_new_sources=True broker_orders=0")
    summary=signed_file(v69_folder/"summary.json",V69,expected_fingerprint)
    if (summary["broker_orders"]!=0 or summary["chunks"]!=1 or
            len(summary["chunk_summaries"])!=1 or
            summary["chunk_summaries"][0]["status"]!="SOURCE_CHECKED_AND_REPLAYED"):
        raise V74Error("V74_PARENT_SOURCE_CENSUS_NOT_REPLAYED")
    chunk=signed_file(v69_folder/"chunk_0001.summary.json",V69,
                      summary["chunk_summaries"][0]["fingerprint"])
    before=signed_file(v69_folder/"chunk_0001.preflight.json",V65,
                       chunk["original_v65_preflight_sha"])
    after=signed_file(v69_folder/"chunk_0001.replay.json",V65,
                      chunk["original_v65_post_source_sha"])
    receipt=signed_file(v69_folder/"chunk_0001.sources.json",V69)
    if (receipt["original_preflight_sha"]!=before["fingerprint"]
            or chunk["source_resolution"]!=receipt["runtime_source_receipt"]
            or summary["start"][:7]!=summary["end"][:7]
            or after["provider_requests"]!=0
            or after["broker_orders"]!=0):
        raise V74Error("V74_CHAIN_SOURCE_IDENTITY_INVALID")
    prior={r["session"]:r for r in before["session_reports"]}
    rows=after["session_reports"]
    if len(rows)!=len(prior) or not rows or [r["session"] for r in rows]!=sorted(prior):
        raise V74Error("V74_SOURCE_SESSION_COVERAGE_INVALID")
    for row in rows:
        old=prior[row["session"]]
        if (not verified(row) or not verified(old)
                or row["native_minute_source_sha256"]!=old["native_minute_source_sha256"]
                or row["signal_fingerprint"]!=old["signal_fingerprint"]
                or row["selected_contract"]!=old["selected_contract"]
                or row["exact_option_requirement"]!=old["exact_option_requirement"]):
            raise V74Error("V74_NATIVE_SIGNAL_OR_ORIGINAL_SELECTION_CHANGED")
    emit(f"START V74 source_sessions={len(rows)} "
         f"brokers={','.join(BROKERS)} action_lag_seconds={action_lag_seconds} source=SHA_VERIFIED_CACHE_ONLY "
         "fills=0 provider_calls=0")
    setting=settings_factory(ROOT,"development")
    reports={b:[] for b in BROKERS}
    cache={}
    total=len(rows)*len(BROKERS)
    completed=0
    milestone=10
    output_dir.mkdir(parents=True,exist_ok=False)
    for row in rows:
        q=row["exact_option_receipt"]
        req=row["exact_option_requirement"]
        if q is None and req is not None or q is not None and req is None:
            raise V74Error("V74_INVALID_ORIGINAL_REQUIREMENT_RECEIPT")
        source=None
        original_blocked=(q is not None and q["state"]!="ARCHIVED")
        if q is not None and not original_blocked:
            qid=q["query_id"]
            if qid not in cache:
                emit(f"STAGE_START V74 SHA-verify original options archive "
                     f"date={row['session']} query={qid} provider_calls=0")
                try:
                    data=source_reader(setting,qid)
                except Exception as exc:
                    raise V74Error("V74_ORIGINAL_ARCHIVE_READ_FAILED") from exc
                if data.get("cache_evidence")!="CACHE_HIT":
                    raise V74Error("V74_ORIGINAL_ARCHIVE_MISSING_REQUIRES_SOURCE")
                cache[qid]=data["source"]
            source=cache[qid]
        for broker in BROKERS:
            if original_blocked:
                result=signed({
                    "contract":CONTRACT,"session":row["session"],
                    "broker_research_policy":broker,
                    "status":"SOURCE_UNRESOLVED",
                    "reason":"EXPLICIT_ORIGINAL_SOURCE_NOT_ARCHIVED",
                    "parent_v65_sha":row["fingerprint"],
                    "original_state":q["state"],"original_query_id":q["query_id"],
                    "entry_debit":None,"exit_credit":None,"trade_net_pnl":None,
                    "events":[],"actual_broker_fills":0,"provider_requests":0,
                })
            else:
                result=replay(row,source,broker=broker,
                              action_lag_seconds=action_lag_seconds)
            path=output_dir/f"{broker}_{row['session']}.json"
            stored=write_once(path,{k:v for k,v in result.items() if k!="fingerprint"})
            reports[broker].append({
                "session":row["session"],"status":result["status"],
                "reason":result["reason"],"fingerprint":stored["fingerprint"],
                "entry_debit":result.get("entry_debit"),
                "trade_net_pnl":result.get("trade_net_pnl"),
                "parent_v65_sha":row["fingerprint"],
            })
            completed+=1
            while milestone<=100 and 100*completed>=milestone*total:
                emit(f"PROGRESS_{milestone}PCT V74 completed={completed}/{total} "
                     f"last_session={row['session']} broker={broker} "
                     f"status={result['status']}")
                milestone+=10
    profiles={}
    for broker in BROKERS:
        cash=Decimal("25000")
        blocked_at=None
        ledger=[]
        for item in reports[broker]:
            if blocked_at is not None:
                ledger.append({"session":item["session"],
                               "account_state":"CENSORED_AFTER_UNRESOLVED",
                               "settled_cash":None})
                continue
            if item["status"] in ("NO_SIGNAL","NO_ENTRY"):
                pnl=Decimal("0")
            elif item["status"]=="CLOSED_QUOTE_REFERENCE":
                pnl=Decimal(item["trade_net_pnl"])
                if Decimal(item["entry_debit"])>cash:
                    blocked_at=item["session"]
                    ledger.append({"session":item["session"],
                                   "account_state":"FROZEN_ENTRY_CASH_INSUFFICIENT",
                                   "settled_cash":None})
                    continue
            else:
                blocked_at=item["session"]
                ledger.append({"session":item["session"],
                               "account_state":"UNRESOLVED_OR_MISSING_ORIGINAL",
                               "settled_cash":None})
                continue
            cash+=pnl
            ledger.append({"session":item["session"],
                           "account_state":item["status"],
                           "settled_cash":str(cash),
                           "realized_quote_pnl":str(pnl)})
        count=Counter(x["status"] for x in reports[broker])
        profiles[broker]={
            "status_counts":dict(sorted(count.items())),
            "cash_censored_at":blocked_at,
            "last_defensible_settled_cash":str(cash),
            "fully_resolved_period_cash":str(cash) if blocked_at is None else None,
            "historical_alpha_proven":False,
            "quote_reference_only":True,
            "days":reports[broker],"account_ledger":ledger,
        }
    final=write_once(output_dir/"summary.json",{
        "contract":CONTRACT,
        "status":"COMPLETE_OFFLINE_ORIGINAL_DYNAMIC_EXIT_REPLAY",
        "original_v69_sha":summary["fingerprint"],
        "experimental_exit_action_lag_seconds":action_lag_seconds,
        "original_v69_date_range":[summary["start"],summary["end"]],
        "profiles":profiles,
        "no_broker_submissions_or_exercise_instructions":True,
        "no_new_provider_requests_or_retries":True,
        "original_1s_1pct_entry_policy_frozen":True,
        "broker_specific_expiry_law_or_fill_not_claimed":True,
        "quote_reference_not_real_broker_fills":True,
        "provider_requests":0,"broker_orders":0,
    })
    emit(f"COMPLETE V74 sessions={len(rows)} "
         f"webull_closed={profiles['webull']['status_counts'].get('CLOSED_QUOTE_REFERENCE',0)} "
         f"alpaca_closed={profiles['alpaca']['status_counts'].get('CLOSED_QUOTE_REFERENCE',0)} "
         f"output={output_dir/'summary.json'} broker_orders=0 provider_calls=0")
    return final


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v69-folder",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--expected-v69-fingerprint",required=True)
    p.add_argument("--exit-action-lag-seconds",type=int,choices=(1,3),default=1)
    a=p.parse_args(argv)
    try:
        review(a.v69_folder,a.output_dir,
               expected_fingerprint=a.expected_v69_fingerprint,
               action_lag_seconds=a.exit_action_lag_seconds)
        return 0
    except Exception as exc:
        event(f"STOPPED V74 reason_type={type(exc).__name__} "
              "broker_orders=0 provider_requests=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
