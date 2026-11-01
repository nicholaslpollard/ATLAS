from __future__ import annotations

"""V93 offline fail-closed original 2018-2023 source campaign prerequisite.

Before any historical option GET: verify user's immutable V92 signed evidence
by exact SHA, and rehash BOTH original stock files for all 72 calendar months.
This script imports no option provider or brokerage client.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import discover_minute_units,verify_unit_integrity
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v93-frozen-original-source-preflight-2018-through-2023-v1"
EXPECTED_V92_INVENTORY_SHA="e19d03c45847e48b536d6eab16331aa752ae296b525484693cc210e63528f0e9"
EXPECTED_V92_SUMMARY_SHA="96d819a0b31d6c1ee436eeda7644871e9e425a6513a719e18b05084218f180c4"
YEARS=tuple(range(2018,2024))


class V93Error(ValueError):
    pass


def verified(doc):
    return (isinstance(doc,dict) and doc.get("fingerprint")==_fingerprint({
        k:v for k,v in doc.items() if k!="fingerprint"
    }))


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def read(path):
    if not path.is_file() or path.is_symlink():
        raise V93Error("V93_ORIGINAL_V92_DOCUMENT_UNAVAILABLE")
    obj=json.loads(path.read_text(encoding="utf8"))
    if not verified(obj):
        raise V93Error("V93_V92_ORIGINAL_FINGERPRINT_CHANGED")
    return obj


def write_once(path,doc):
    item=signed(doc)
    with path.open("x",encoding="utf8") as out:
        json.dump(item,out,indent=2,sort_keys=True,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return item


def preflight(source_dir,*,layout=None,discover=discover_minute_units,
              verify=verify_unit_integrity):
    original=read(source_dir/"original_month_inventory.json")
    summary=read(source_dir/"summary.json")
    if (original["fingerprint"]!=EXPECTED_V92_INVENTORY_SHA
            or summary["fingerprint"]!=EXPECTED_V92_SUMMARY_SHA
            or summary["inventory_sha"]!=original["fingerprint"]
            or original["contract"]!="atlas-v92-pre2024-original-spy-monthly-minute-inventory-v1-month-inventory-v1"
            or summary["contract"]!="atlas-v92-pre2024-original-spy-monthly-minute-inventory-v1"
            or original["date_boundary_start"]!="2018-01-01"
            or original["date_boundary_end"]!="2023-12-31"
            or original["no_option_data_accessed"] is not True
            or original["no_provider_or_broker_clients"] is not True
            or summary["months_examined"]!=72
            or summary["available_original_spy_months_full_sha_verified"]!=72
            or summary["absent_or_invalid_months"]!=0
            or len(original["months"])!=72
            or summary["broker_orders"]!=0
            or summary["provider_requests"]!=0):
        raise V93Error("V93_FROZEN_V92_EVIDENCE_ROOTS_OR_CENSUS_MISMATCH")
    by_month={}
    for m in original["months"]:
        year,month=m["year"],m["month"]
        key=(year,month)
        if (year not in YEARS or type(month) is not int or not 1<=month<=12
                or key in by_month or
                m["status"]!="ORIGINAL_FULL_SHA_VERIFIED"
                or m["original_full_sha_verified"] is not True
                or any(not isinstance(m.get(k),str) or len(m[k])!=64 for k in
                       ("canonical_sha256","raw_bundle_sha256"))):
            raise V93Error("V93_V92_MONTH_NOT_QUALIFIED")
        by_month[key]=m
    required={(y,m) for y in YEARS for m in range(1,13)}
    if set(by_month)!=required:
        raise V93Error("V93_V92_MONTH_GAP_OR_EXTRA")
    layout=layout or V2Layout.beneath(ROOT/"data")
    observations=[]
    for year,month in sorted(required):
        m=by_month[(year,month)]
        units=[u for u in discover(layout,target_year=year,target_month=month,
                                   progress=None)
               if (u.year,u.month)==(year,month) and "SPY" in u.symbols]
        if len(units)!=1:
            raise V93Error("V93_LOCAL_ORIGINAL_SPY_UNIT_NOT_UNIQUE")
        unit=units[0]
        if (unit.unit_id!=m["unit_id"]
                or unit.canonical_sha256!=m["canonical_sha256"]
                or unit.raw_bundle_sha256!=m["raw_bundle_sha256"]
                or unit.canonical_path.is_symlink() or unit.raw_bundle_path.is_symlink()
                or unit.checkpoint_path.is_symlink()
                or not verify(unit)["accepted"]):
            raise V93Error("V93_LOCAL_SOURCE_BYTES_DIFFER_FROM_V92")
        observations.append({
            "year":year,"month":month,"unit_id":unit.unit_id,
            "canonical_sha256":unit.canonical_sha256,
            "raw_bundle_sha256":unit.raw_bundle_sha256,
            "original_file_bytes_rehashed_at_gate":True,
        })
    return original,summary,observations


def run(source_dir,output,*,layout=None,discover=discover_minute_units,
        verify=verify_unit_integrity,reporter=print):
    if output.exists() or output.is_symlink():
        raise V93Error("V93_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    original,prior,observations=preflight(source_dir,layout=layout,discover=discover,
                                          verify=verify)
    output.mkdir(parents=True,exist_ok=False)
    receipt=write_once(output/"preflight.json",{
        "contract":CONTRACT,
        "original_v92_inventory_sha":original["fingerprint"],
        "original_v92_summary_sha":prior["fingerprint"],
        "full_source_months_sha_reverified":len(observations),
        "month_source_observations":observations,
        "historical_cohorts":[{"year":year,
                               "start":f"{year}-01-01",
                               "end":f"{year}-12-31"}
                              for year in YEARS],
        "six_original_strategies_unchanged":True,
        "user_2018_2023_cohort_inclusion_frozen_before_new_outcomes":True,
        "no_option_data_acquired_or_outcomes_read":True,
        "source_bar_session_completeness_not_yet_guaranteed":True,
        "protected_master_2026_holdout_accessed":False,
        "provider_calls":0,"broker_orders":0,
    })
    reporter(f"COMPLETE V93 PRE-ACQUISITION original_v92_sha_verified=True "
             f"original_stock_months_rehashed={len(observations)} "
             "provider_calls=0 broker_orders=0")
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v92-source-dir",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        run(args.v92_source_dir,args.output_dir)
        return 0
    except Exception as exc:
        print(f"STOP V93 PRE-ACQUISITION type={type(exc).__name__} "
              "no_provider_or_broker_calls=True",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
