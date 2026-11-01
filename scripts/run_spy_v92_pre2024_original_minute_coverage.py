from __future__ import annotations

"""V92: inventory original locally held SPY minute partitions, 2018–2023.

Read-only. Never constructs option SDK clients, never requests provider data,
never reads 2024+ or the sealed 2026 holdout. Audit the *entire* canonical
and original raw file SHA-256 for any candidate SPY month. Availability of
monthly files is NOT proof every individual session has ten causal bars.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    discover_minute_units,verify_unit_integrity,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v92-pre2024-original-spy-monthly-minute-inventory-v1"


class V92Error(ValueError):
    pass


def signed(value):
    return {**value,"fingerprint":_fingerprint(value)}


def verified(value):
    return (isinstance(value,dict) and value.get("fingerprint")==_fingerprint(
        {k:v for k,v in value.items() if k!="fingerprint"}))


def write_once(path,value):
    doc=signed(value)
    with path.open("x",encoding="utf8") as out:
        json.dump(doc,out,indent=2,sort_keys=True,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return doc


def run(out_dir,*,layout=None,discover=discover_minute_units,
        verifier=verify_unit_integrity,start_year=2018,end_year=2023,
        reporter=print):
    if (type(start_year) is not int or type(end_year) is not int
            or not 2018<=start_year<=end_year<=2023
            or out_dir.exists() or out_dir.is_symlink()):
        raise V92Error("V92_OUTSIDE_FROZEN_PRE2024_BOUNDARY_OR_OUTPUT_EXISTS")
    layout=layout or V2Layout.beneath(ROOT/"data")
    root=layout.checkpoints/"native_units"/"1m"
    months=[]
    counts=Counter()
    out_dir.mkdir(parents=True,exist_ok=False)
    for y in range(start_year,end_year+1):
        for m in range(1,13):
            monthroot=root/f"year={y:04d}"/f"month={m:02d}"
            item={"year":y,"month":m,"status":None,"unit_id":None,
                  "canonical_sha256":None,"raw_bundle_sha256":None,
                  "source_unit_count":0,"original_full_sha_verified":False,
                  "session_minutes_not_yet_audited":True,
                  "provider_requests":0,"broker_orders":0}
            if monthroot.is_symlink():
                item["status"]="REJECTED_SYMLINK_MONTH"
            elif not monthroot.is_dir():
                item["status"]="MONTH_NOT_PRESENT_LOCALLY"
            else:
                try:
                    available=discover(layout,target_year=y,target_month=m,
                                       progress=None)
                    units=[u for u in available
                           if u.year==y and u.month==m and "SPY" in u.symbols]
                    item["source_unit_count"]=len(units)
                    if not units:
                        item["status"]="NO_COMPLETE_SPY_CHECKPOINT"
                    elif len(units)!=1:
                        item["status"]="AMBIGUOUS_SPY_SOURCE_UNITS"
                    else:
                        unit=units[0]
                        item.update({
                            "unit_id":unit.unit_id,
                            "canonical_sha256":unit.canonical_sha256,
                            "raw_bundle_sha256":unit.raw_bundle_sha256,
                        })
                        if (unit.canonical_path.is_symlink()
                                or unit.raw_bundle_path.is_symlink()
                                or unit.checkpoint_path.is_symlink()):
                            item["status"]="REJECTED_SYMLINK_ORIGINAL_FILE"
                        else:
                            tested=verifier(unit)
                            item["status"]=(
                                "ORIGINAL_FULL_SHA_VERIFIED" if tested["accepted"]
                                else "SOURCE_SHA_OR_FILE_INVALID"
                            )
                            item["original_full_sha_verified"]=bool(tested["accepted"])
                            if not tested["accepted"]:
                                item["error_count"]=len(tested.get("errors",[]))
                except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
                    item["status"]="SOURCE_CHECKPOINT_REVIEW_REQUIRED"
                    item["error_type"]=type(exc).__name__
            counts[item["status"]]+=1
            months.append(item)
            reporter(f"V92_MONTH {y}-{m:02d} status={item['status']} "
                     f"verified={item['original_full_sha_verified']} "
                     "provider_calls=0 broker_orders=0")
    record=write_once(out_dir/"original_month_inventory.json",{
        "contract":CONTRACT+"-month-inventory-v1",
        "date_boundary_start":f"{start_year:04d}-01-01",
        "date_boundary_end":f"{end_year:04d}-12-31",
        "months":months,"counts":dict(sorted(counts.items())),
        "no_provider_or_broker_clients":True,
        "no_option_data_accessed":True,
        "protected_master_holdout_2026_may_aug_unaccessed":True,
    })
    result=write_once(out_dir/"summary.json",{
        "contract":CONTRACT,
        "inventory_sha":record["fingerprint"],
        "months_examined":len(months),
        "available_original_spy_months_full_sha_verified":
            counts["ORIGINAL_FULL_SHA_VERIFIED"],
        "absent_or_invalid_months":len(months)-counts["ORIGINAL_FULL_SHA_VERIFIED"],
        "counts":dict(sorted(counts.items())),
        "all_sessions_have_causally_closed_opening_minutes_proven":False,
        "requires_full_v89_session_stock_causality_audit_before_any_option_calls":True,
        "no_strategy_profit_outcomes_observed":True,
        "provider_requests":0,"broker_orders":0,
        "master_holdout_accessed":False,
    })
    reporter(f"COMPLETE V92 original_SPY_months_sha_verified="
             f"{counts['ORIGINAL_FULL_SHA_VERIFIED']}/{len(months)} "
             "provider_calls=0 broker_orders=0")
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--start-year",type=int,default=2018)
    p.add_argument("--end-year",type=int,default=2023)
    args=p.parse_args(argv)
    try:
        run(args.output_dir,start_year=args.start_year,end_year=args.end_year)
        return 0
    except Exception as exc:
        print(f"STOP V92 type={type(exc).__name__} "
              "zero_provider_and_broker_calls=True",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
