from __future__ import annotations

"""V104: original-V103-anchored exact missing-quote acquisition + exit diagnosis.

Frozen original V55 entry/exit policy; no brokerage operations. Historical
ThetaData acquisition is ONLY for original exact query IDs absent from the
signed V103 source census; V39/V38 rechecks actual persistent cache state
and prohibits same-query retry after ambiguous provider dispatch.
"""
import argparse
from collections import Counter
from datetime import date
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
from packages.simulation.strategy_options_source_runtime_v39 import (
    resolve_strategy_source_demands,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "atlas-v104-v103-exact-missing-orb-source-and-exit-audit-v1"
ORIGINAL_V103_ROOT_SHA = "15ffac1de97473c2ef3d924b6a84a22b8fa5342edeab79e182238ca69faa861b"
ORIGINAL_FULL_ZIP_SHA = "79e9421b1e25f92aad55b979518d9b022826c6f334cc773c873df1f20afb4aa5"
V65 = "atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
STRATEGY = "V104_V103_2026_MISSING_EXACT_1S_ORB"
SHA64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_MONTHS = tuple(f"2025-{i:02d}" for i in range(6,13)) + tuple(
    f"2026-{i:02d}" for i in range(1,5)
)


class V104Error(ValueError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified(item: dict) -> bool:
    return (isinstance(item, dict) and SHA64.fullmatch(str(item.get("fingerprint", "")))
            is not None and item["fingerprint"] == _fingerprint({
                k:v for k,v in item.items() if k!="fingerprint"}))


def signed(item: dict) -> dict:
    return {**item, "fingerprint": _fingerprint(item)}


def write_once(path: Path, item: dict) -> dict:
    if path.exists() or path.is_symlink():
        raise V104Error("V104_IMMUTABLE_FILE_ALREADY_EXISTS")
    doc = signed(item)
    with path.open("x", encoding="utf8") as stream:
        json.dump(doc, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return doc


def read_original_v103(full_zip: Path, *, required_original_sha: str=ORIGINAL_FULL_ZIP_SHA):
    """Verify source-linked original parent ZIP and all 11 signed gzip journals."""
    if full_zip.is_symlink() or not full_zip.is_file():
        raise V104Error("V104_ORIGINAL_V103_ZIP_NOT_FOUND")
    actual_sha=hashlib.sha256()
    with full_zip.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            actual_sha.update(block)
    if required_original_sha and actual_sha.hexdigest()!=required_original_sha:
        raise V104Error("V104_ORIGINAL_ZIP_SHA_MISMATCH")
    reports={}
    with zipfile.ZipFile(full_zip) as archive:
        if archive.testzip() is not None:
            raise V104Error("V104_ZIP_CRC_FAILED")
        lookup={}
        for raw_name in archive.namelist():
            name=raw_name.replace("\\","/")
            if (name in lookup or name.startswith("/") or ".." in name.split("/")
                    or name.endswith("/")):
                raise V104Error("V104_UNSAFE_OR_DUPLICATE_ZIP_MEMBER")
            lookup[name]=raw_name
        expected_names={"summary.json","chronological_account.json"}
        expected_names|={f"months/v103_account_{m.replace('-','')}.json"
                         for m in EXPECTED_MONTHS}
        expected_names|={f"months/v65_original_{m.replace('-','')}.json.gz"
                         for m in EXPECTED_MONTHS}
        if set(lookup)!=expected_names:
            raise V104Error("V104_ORIGINAL_ZIP_MEMBERS_CHANGED")
        summary=json.loads(archive.read(lookup["summary.json"]))
        if (not verified(summary) or summary.get("fingerprint")!=ORIGINAL_V103_ROOT_SHA
                or summary.get("months")!=11 or summary.get("exchange_sessions")!=230
                or summary.get("zero_option_provider_calls") is not True
                or summary.get("zero_broker_orders") is not True
                or summary.get("window_end")!="2026-04-30"):
            raise V104Error("V104_ORIGINAL_V103_ROOT_FINGERPRINT_OR_SCOPE_INVALID")
        chrono=json.loads(archive.read(lookup["chronological_account.json"]))
        if (not verified(chrono) or not verified(chrono.get("account"))
                or chrono["fingerprint"]!=summary["combined_account_sha"]
                or len(chrono["account"].get("all_sessions",[]))!=230
                or chrono["account"].get("actual_broker_orders")!=0):
            raise V104Error("V104_ORIGINAL_230_SESSION_ACCOUNT_PARENT_NOT_SIGNED")
        for event in chrono["account"]["all_sessions"]:
            if not verified(event):
                raise V104Error("V104_ORIGINAL_CHRONOLOGICAL_SESSION_SHA_INVALID")
        by_receipt={r["month"]:r for r in summary["original_V65_gzip_receipts"]}
        by_month={r["month"]:r for r in summary["monthly_source_linked_accounts"]}
        if set(by_receipt)!=set(EXPECTED_MONTHS) or set(by_month)!=set(EXPECTED_MONTHS):
            raise V104Error("V104_MISSING_OR_DUPLICATED_PARENT_MONTH")
        for month in EXPECTED_MONTHS:
            token=month.replace("-","")
            rec=by_receipt[month]
            compressed=archive.read(lookup[f"months/v65_original_{token}.json.gz"])
            if (len(compressed)!=rec["compressed_bytes"]
                    or sha_bytes(compressed)!=rec["gzip_sha256"]):
                raise V104Error("V104_ORIGINAL_MONTH_GZIP_SHA_MISMATCH")
            raw=gzip.decompress(compressed)
            if len(raw)!=rec["raw_bytes"] or sha_bytes(raw)!=rec["raw_sha256"]:
                raise V104Error("V104_ORIGINAL_MONTH_RAW_SHA_MISMATCH")
            original=json.loads(raw)
            if (not verified(original) or original["fingerprint"]!=rec["original_v65_sha"]
                    or original.get("contract")!=V65
                    or original.get("provider_requests")!=0 or original.get("broker_orders")!=0):
                raise V104Error("V104_ORIGINAL_V65_PARENT_NOT_SIGNED")
            account=json.loads(archive.read(lookup[f"months/v103_account_{token}.json"]))
            if (not verified(account) or not verified(account.get("account"))
                    or account["fingerprint"]!=by_month[month]["report_sha"]
                    or account["account"]["fingerprint"]!=by_month[month]["account_sha"]
                    or account["original_v65_sha"]!=original["fingerprint"]):
                raise V104Error("V104_ORIGINAL_V103_MONTH_ACCOUNT_PARENT_INVALID")
            reports[month]=original
    return summary,reports,actual_sha.hexdigest()


def frozen_missing_and_exits(reports, *, normalize=normalize_source_requirement):
    """Do not assume V55 NO_ENTRY means source-complete or a $0 trade."""
    missing=[]
    unresolved=[]
    candidate_dates=set()
    for month,original in sorted(reports.items()):
        if not verified(original) or original.get("contract")!=V65:
            raise V104Error("V104_SOURCE_JOURNAL_NOT_SIGNED")
        for row in original.get("session_reports",[]):
            day=row.get("session")
            if (not verified(row) or not isinstance(day,str)
                    or day[:7]!=month or day in candidate_dates):
                raise V104Error("V104_SOURCE_SESSION_DUPLICATE_OR_BAD_SHA")
            candidate_dates.add(day)
            trial=row.get("standalone_replay_report")
            if (not verified(trial) or not verified(trial.get("signal"))
                    or trial.get("session")!=day or trial.get("actual_fills")!=0
                    or trial["signal"]["fingerprint"]!=row["signal_fingerprint"]):
                raise V104Error("V104_ORIGINAL_V55_QUOTE_TRIAL_NOT_SIGNED")
            req=row.get("exact_option_requirement")
            receipt=row.get("exact_option_receipt")
            if req is None:
                if receipt is not None:
                    raise V104Error("V104_NO_SOURCE_REQUEST_BUT_HAS_RECEIPT")
                continue
            if not isinstance(receipt,dict):
                raise V104Error("V104_MISSING_SOURCE_RECEIPT")
            checked=normalize(req["method"],req["kwargs"])
            qid=_fingerprint(checked)
            if (req!=checked or receipt.get("query_id")!=qid
                    or checked["kwargs"].get("date_et")!=day
                    or checked["kwargs"].get("expiration")!=day
                    or checked["kwargs"].get("interval")!="1s"
                    or checked["kwargs"].get("symbol")!="SPY"
                    or date.fromisoformat(day)>date(2026,4,30)):
                raise V104Error("V104_SOURCE_IDENTITY_OR_BOUNDARY_DRIFT")
            if receipt.get("state")=="NOT_REGISTERED":
                if (trial["status"]!="NO_ENTRY"
                        or trial["censor_reason"]!="OPTION_SOURCE_MISSING_OR_UNQUALIFIED"):
                    raise V104Error("V104_MISSING_QUERY_NOT_ORIGINAL_CENSORED")
                missing.append({
                    "session":day,"source_query_id":qid,
                    "original_v65_session_sha":row["fingerprint"],
                    "original_v55_signal_sha":row["signal_fingerprint"],
                    "request":checked,
                    "original_cache_state":"NOT_REGISTERED",
                    "same_query_retry_permitted_if_ever_dispatched":False,
                })
            elif receipt.get("state")=="ARCHIVED":
                if (receipt.get("archive_sha256")!=trial.get("source_sha256")
                        or trial.get("source_query_id")!=qid):
                    raise V104Error("V104_ARCHIVED_ORIGINAL_RECEIPT_DRIFT")
            else:
                raise V104Error("V104_NEW_ORIGINAL_PROVIDER_RECEIPT_STATE_REQUIRES_REVIEW")
            if trial.get("status")=="UNRESOLVED_POSITION":
                if trial.get("terminal_equity_if_resolved") is not None:
                    raise V104Error("V104_UNKNOWN_EXIT_FABRICATED_EQUITY")
                events=trial.get("events",[])
                failures=[{
                    "row":e.get("row"),"at_et":e.get("at_et"),
                    "reason":e.get("reason")
                } for e in events if e.get("type")=="EXIT_SOURCE_REJECTION"]
                entry=[e for e in events if e.get("type")=="MODELED_ENTRY_QUOTE_REFERENCE"]
                unresolved.append({
                    "session":day,"source_query_id":qid,
                    "original_v65_session_sha":row["fingerprint"],
                    "original_option_archive_sha":receipt["archive_sha256"],
                    "exit_status":"UNRESOLVED_POSITION",
                    "reason":trial.get("censor_reason"),
                    "entry_debit_usd":trial.get("entry_debit"),
                    "entry_events":len(entry),
                    "exit_source_rejections":failures[:3],
                    "events_examined":len(events),
                    "no_substituted_expiry_or_exit_price":True,
                })
    missing.sort(key=lambda m:m["session"])
    unresolved.sort(key=lambda m:m["session"])
    if (len({x["session"] for x in missing})!=len(missing)
            or len({x["source_query_id"] for x in missing})!=len(missing)):
        raise V104Error("V104_DUPLICATED_MISSING_SOURCES")
    return missing, unresolved, len(candidate_dates)


def demand_items(missing):
    for row in missing:
        req=row["request"]
        yield {
            "candidate_id":"V103_ORB_"+row["session"].replace("-",""),
            "purpose":"required_exact_1s_entry_exit_tape",
            "method":req["method"],"kwargs":dict(req["kwargs"]),
        }


def run(original_zip: Path, output_dir: Path, *, acquire: bool=False,
        resolver=resolve_strategy_source_demands,
        settings_factory=load_settings, reporter=print):
    if output_dir.exists() or output_dir.is_symlink():
        raise V104Error("V104_OUTPUT_EXISTS")
    original,reports,archive_sha=read_original_v103(original_zip)
    missing,unresolved,observed=frozen_missing_and_exits(reports)
    if (len(missing)!=45 or len(unresolved)!=16 or observed!=227
            or any(not x["session"].startswith("2026-") for x in missing)):
        raise V104Error("V104_FROZEN_ORIGINAL_45_SOURCE_AND_16_EXIT_POPULATION_DRIFT")
    output_dir.mkdir(parents=True,exist_ok=False)
    plan=write_once(output_dir/"source_plan.json",{
        "contract":CONTRACT+"-frozen-first-acquisition-demand-v1",
        "original_v103_root_sha":original["fingerprint"],
        "original_v103_zip_sha":archive_sha,
        "original_v65_signed_months":len(reports),
        "missing_exact_query_count":len(missing),
        "missing_source_requirements":missing,
        "no_previously_ambiguous_query_automatically_retried":True,
        "original_entry_and_exit_strategy_unchanged":True,
        "original_2026_master_holdout_unread":True,
    })
    diagnosis=write_once(output_dir/"unresolved_exits.json",{
        "contract":CONTRACT+"-original-censored-exit-diagnosis-v1",
        "original_v103_root_sha":original["fingerprint"],
        "reason_counts":dict(sorted(Counter(e["reason"] for e in unresolved).items())),
        "unresolved":unresolved,
        "no_expiry_cash_or_unsupported_exit_fill_invented":True,
    })
    reporter(f"V104 VERIFIED_SOURCE_PLAN missing={len(missing)} distinct_qids={len(missing)} "
             f"unresolved_exits={len(unresolved)} signed_v65_months={len(reports)}")
    result=None
    if acquire:
        logfile=output_dir/"provider_dispatch_events.jsonl"
        def event(label, details):
            rec={"event":label,"query_id":details.get("query_id"),
                 "date_et":details.get("date_et"),"status":details.get("status"),
                 "error_class":details.get("error"),"counts":details.get("counts")}
            with logfile.open("a",encoding="utf8") as stream:
                stream.write(json.dumps(rec,sort_keys=True,allow_nan=False)+"\n")
                stream.flush()
                os.fsync(stream.fileno())
            if label in ("provider_dispatch","source_failed","source_done","source_blocked"):
                reporter(f"V104 {label} date={rec['date_et']} "
                         f"state={rec['status']} provider_dispatches="
                         f"{rec['counts'].get('provider_dispatch_attempts',0)}")
        settings=settings_factory(ROOT,"development")
        # V39 automatically checks live V38 state; ARCHIVED is a cache hit,
        # NO_DATA and uncertain dispatch are not retried. New query only.
        result=resolver(settings,STRATEGY,list(demand_items(missing)),
                        on_progress=event,continue_on_error=True)
        if (result.get("source_uses_requested")!=45
                or result.get("provider_dispatch_attempts",0)>45):
            raise V104Error("V104_RUNTIME_REQUEST_GRID_DRIFT")
    summary=write_once(output_dir/"summary.json",{
        "contract":CONTRACT,"original_v103_root_sha":original["fingerprint"],
        "source_plan_sha":plan["fingerprint"],
        "unresolved_diagnosis_sha":diagnosis["fingerprint"],
        "original_missing_source_queries":45,
        "historically_unresolved_exit_positions":16,
        "source_acquisition_attempted":acquire,
        "provider_result":result,
        "broker_orders":0,
        "entry_and_exit_policy_changes":0,
        "profitability_proven":False,
        "protected_holdout_access":False,
    })
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-v103-full-zip",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--acquire",action="store_true")
    args=p.parse_args(argv)
    try:
        done=run(args.original_v103_full_zip,args.output_dir,acquire=args.acquire)
        print(f"V104 COMPLETE requested={done['original_missing_source_queries']} "
              f"acquisition={done['source_acquisition_attempted']} "
              f"summary={args.output_dir/'summary.json'} broker_orders=0")
        return 0
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,zipfile.BadZipFile) as exc:
        print(f"V104 STOP error={type(exc).__name__}: {str(exc)[:180]} "
              "broker_orders=0 no_ambiguous_retries=True",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
