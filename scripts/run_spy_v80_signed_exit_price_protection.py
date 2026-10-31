from __future__ import annotations

"""Offline V80 audit of full original V79/V76 event ZIP; zero broker calls.

Source is an immutable ZIP with original V76 monthly summaries and gzipped
signed per-trade event journals. No ZIP extraction, network, or order creation.
"""

import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import zipfile
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v80_exit_price_protection_shadow import (
    BANDS, evaluate,
)

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v80-six-month-signed-exit-price-marketability-audit-v1"
POLICIES=("v74_control","runner_35_150")
LAGS=(1,3)


def emit(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",flush=True)


def signed(payload):
    return {**payload,"fingerprint":_fingerprint(payload)}


def checked(payload):
    if (not isinstance(payload,dict) or payload.get("fingerprint")!=
            _fingerprint({k:v for k,v in payload.items() if k!="fingerprint"})):
        raise ValueError("V80_SIGNED_SOURCE_DOCUMENT_INVALID")
    return payload


def stored(path,payload):
    document=signed(payload)
    with path.open("x",encoding="utf8") as fh:
        json.dump(document,fh,sort_keys=True,indent=2,allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return document


def run(source_zip,output_dir,*,callback=emit):
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("V80_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    if not source_zip.is_file() or source_zip.is_symlink():
        raise ValueError("V80_ORIGINAL_EVIDENCE_ZIP_REQUIRED")
    callback("STAGE_START V80 original ZIP signed SHA and path validation "
             "provider_calls=0 broker_orders=0")
    root=hashlib.sha256(source_zip.read_bytes()).hexdigest()
    with zipfile.ZipFile(source_zip) as archive:
        archive_members=archive.namelist()
        mapped={n.replace("\\","/"):n for n in archive_members}
        months={}
        for mapped_name,raw_name in mapped.items():
            if mapped_name.endswith("/summary.json"):
                month=mapped_name.split("/")[-2]
                if month in months:
                    raise ValueError("V80_DUPLICATE_SOURCE_MONTH")
                months[month]=checked(json.loads(archive.read(raw_name)))
        if sorted(months)!=[
            "202507","202508","202509","202510","202511","202512"
        ]:
            raise ValueError("V80_REQUIRED_SIX_MONTH_MANIFESTS_NOT_FOUND")
        pending=[]
        for month,manifest in sorted(months.items()):
            if (manifest["provider_calls"]!=0 or
                    manifest["broker_orders"]!=0 or
                    manifest["actual_historical_broker_option_fills"]!=0):
                raise ValueError("V80_EXISTING_BROKER_EXECUTION_STATE_UNEXPECTED")
            for policy in manifest["policies"]:
                if policy["name"] not in POLICIES:
                    continue
                if policy["lag_seconds"] not in LAGS:
                    raise ValueError("V80_UNEXPECTED_LAG")
                for row in policy["daily_event_receipts"]:
                    if row["status"] in ("NO_SIGNAL","NO_ENTRY"):
                        continue
                    filename=row["stored_file"]
                    if (filename!=filename.split("/")[-1].split("\\")[-1] or
                            not filename.endswith(".json.gz")):
                        raise ValueError("V80_UNSAFE_ORIGINAL_SOURCE_FILENAME")
                    candidates=[k for k in mapped if k.endswith(
                        f"/{month}/{filename}")]
                    if len(candidates)!=1:
                        raise ValueError("V80_SOURCE_JOURNAL_NOT_UNIQUE")
                    pending.append((month,policy,row,mapped[candidates[0]]))
        if len(pending)!=244:
            raise ValueError("V80_EXPECTED_244_ENTERED_ORIGINAL_EVENTS")
        callback(f"STAGE_PASS V80 six_signed_months=6 "
                 f"original_journals_to_verify={len(pending)}")
        original_seen=set()
        results=[]
        ticks=10
        for i,(month,policy,row,archive_name) in enumerate(pending,1):
            compressed=archive.read(archive_name)
            if hashlib.sha256(compressed).hexdigest()!=row["stored_gzip_sha256"]:
                raise ValueError("V80_COMPRESSED_ORIGINAL_SHA_MISMATCH")
            document=checked(json.loads(gzip.decompress(compressed)))
            if (document["fingerprint"]!=row["event_report_sha"] or
                    document["parent_v65_sha"]!=row["original_row_fingerprint"] or
                    document["session"]!=row["session"] or
                    document["status"]!=row["status"] or
                    document["reason"]!=row["reason"] or
                    document["trade_net_pnl"]!=row["net_pnl"] or
                    document["policy"]!=policy["name"] or
                    document["lag_seconds"]!=policy["lag_seconds"]):
                raise ValueError("V80_SOURCE_MANIFEST_IDENTITY_MISMATCH")
            case=(document["session"],document["policy"],document["lag_seconds"])
            if case in original_seen:
                raise ValueError("V80_DUPLICATE_ORIGINAL_DAY_POLICY")
            original_seen.add(case)
            for band in BANDS:
                observation=evaluate(document,max_adverse_pct=band)
                results.append({
                    "session":document["session"],
                    "policy":document["policy"],
                    "lag_seconds":document["lag_seconds"],
                    "registered_adverse_pct":band,
                    "quote_marketability_status":observation["status"],
                    "original_v76_sha":document["fingerprint"],
                    "v80_event_sha":observation["fingerprint"],
                    "trigger_bid":observation.get("trigger_bid"),
                    "action_bid":observation.get("action_bid"),
                    "adverse_bid_drift_pct":observation.get("adverse_bid_drift_pct"),
                    "original_quote_pnl_not_broker_pnl":document["trade_net_pnl"],
                    "actual_broker_orders":0,
                    "realized_cash":None,
                })
            while ticks<=100 and i*100>=ticks*len(pending):
                callback(f"PROGRESS_{ticks}PCT V80 verified={i}/{len(pending)} "
                         f"month={month} last_day={document['session']} "
                         "no_source_queries=True broker_orders=0")
                ticks+=10
        callback("STAGE_START V80 write signed price protection summaries "
                 "original_sources_read_only=True")
        output_dir.mkdir(parents=True,exist_ok=False)
        counts={}
        for policy in POLICIES:
            for lag in LAGS:
                for band in BANDS:
                    subset=[x for x in results if x["policy"]==policy and
                            x["lag_seconds"]==lag and
                            x["registered_adverse_pct"]==band]
                    key=f"{policy}_{lag}s_{band}pct"
                    counts[key]=dict(sorted(Counter(
                        x["quote_marketability_status"] for x in subset
                    ).items()))
        summary=stored(output_dir/"summary.json",{
            "contract":CONTRACT,
            "original_zip_sha256":root,
            "month_manifest_signatures":{m:x["fingerprint"] for m,x in sorted(months.items())},
            "original_journals_sha_and_signature_verified":len(pending),
            "scenarios_written":len(results),
            "quotes_are_not_broker_fills":True,
            "broker_orders":0,"provider_calls":0,
            "actual_realized_option_pnl":None,
            "marketability_counts":counts,
            "source_policy":"ORIGINAL_CACHED_ARCHIVE_READ_ONLY",
        })
        stored(output_dir/"daily_price_protection.json",{
            "contract":CONTRACT+"-daily-v1",
            "parent_summary_sha":summary["fingerprint"],
            "rows":results,
        })
        callback(f"COMPLETE V80 original_events={len(pending)} "
                 f"scenario_cases={len(results)} out={output_dir/'summary.json'} "
                 "broker_orders=0 provider_calls=0")
        return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-journal-zip",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.original_journal_zip,args.output_dir)
        return 0
    except Exception as exc:
        emit(f"STOPPED V80 reason_type={type(exc).__name__} "
             "broker_orders=0 original_file_unchanged=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
