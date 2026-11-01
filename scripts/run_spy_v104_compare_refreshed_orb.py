from __future__ import annotations

"""Compare refreshed V103 replay against frozen signed original entry signals.

Evidence only; no calls to providers or brokers. Original 2025 V55 replay
must remain byte-identical at the per-session signed V55 layer.
"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
from scripts.run_spy_v104_original_orb_source_recovery import (
    CONTRACT, V104Error, read_original_v103, verified, write_once,
    EXPECTED_MONTHS,
)


def compare(original_zip:Path, refreshed_dir:Path, output:Path):
    original_summary,original_reports,zip_sha=read_original_v103(original_zip)
    summary_file=refreshed_dir/"summary.json"
    if summary_file.is_symlink() or not summary_file.is_file():
        raise V104Error("V104_REFRESHED_SUMMARY_MISSING")
    refreshed_summary=json.loads(summary_file.read_text(encoding="utf8"))
    if (not verified(refreshed_summary)
            or refreshed_summary.get("window_start")!="2025-06-01"
            or refreshed_summary.get("window_end")!="2026-04-30"
            or refreshed_summary.get("zero_option_provider_calls") is not True
            or refreshed_summary.get("zero_broker_orders") is not True
            or refreshed_summary.get("months")!=11):
        raise V104Error("V104_REFRESHED_V103_SCOPE_INVALID")
    counts=Counter()
    by_month={}
    qids_changed=[]
    all_source_shas=[]
    for month in EXPECTED_MONTHS:
        token=month.replace("-","")
        original=original_reports[month]
        path=refreshed_dir/"months"/f"v65_original_{token}.json.gz"
        if path.is_symlink() or not path.is_file():
            raise V104Error("V104_REFRESHED_V65_SOURCE_MISSING")
        rec=next((x for x in refreshed_summary["original_V65_gzip_receipts"]
                  if x["month"]==month),None)
        if rec is None:
            raise V104Error("V104_REFRESHED_GZIP_RECEIPT_MISSING")
        import hashlib
        compressed=path.read_bytes()
        raw=gzip.decompress(compressed)
        if (hashlib.sha256(compressed).hexdigest()!=rec["gzip_sha256"]
                or hashlib.sha256(raw).hexdigest()!=rec["raw_sha256"]
                or len(raw)!=rec["raw_bytes"]):
            raise V104Error("V104_REFRESHED_SOURCE_BYTE_SHA_DRIFT")
        changed=json.loads(raw)
        if (not verified(changed) or changed["fingerprint"]!=rec["original_v65_sha"]
                or changed.get("provider_requests")!=0):
            raise V104Error("V104_REFRESHED_V65_SHA_NOT_VERIFIED")
        older={x["session"]:x for x in original["session_reports"]}
        newer={x["session"]:x for x in changed["session_reports"]}
        if len(older)!=len(newer) or set(older)!=set(newer):
            raise V104Error("V104_ORIGINAL_2025_2026_SESSION_POPULATION_CHANGED")
        source_changed=0
        outcomes=Counter()
        for day,old in sorted(older.items()):
            now=newer[day]
            if (not verified(now) or old["signal_fingerprint"]!=now["signal_fingerprint"]
                    or old["selected_contract"]!=now["selected_contract"]
                    or old["exact_option_requirement"]!=now["exact_option_requirement"]
                    or old["native_minute_source_sha256"]!=now["native_minute_source_sha256"]
                    or old["signal_decision_at_et"]!=now["signal_decision_at_et"]):
                raise V104Error("V104_FROZEN_ORIGINAL_ENTRY_SIGNAL_CHANGED")
            if day.startswith("2025-") and (
                    old["standalone_replay_report"]["fingerprint"]
                    != now["standalone_replay_report"]["fingerprint"]):
                raise V104Error("V104_PRIOR_2025_MODEL_OR_SOURCE_RESULT_CHANGED")
            old_state=(old.get("exact_option_receipt") or {}).get("state")
            new_state=(now.get("exact_option_receipt") or {}).get("state")
            if old_state!=new_state:
                if old_state!="NOT_REGISTERED" or not day.startswith("2026-"):
                    raise V104Error("V104_NON_MISSING_OR_PRE2026_SOURCE_DRIFT")
                qids_changed.append({
                    "session":day,"query_id":now["exact_option_receipt"]["query_id"],
                    "old_state":old_state,"new_state":new_state,
                    "new_replay_status":now["standalone_replay_report"]["status"]
                })
                source_changed+=1
            else:
                if old_state=="ARCHIVED" and old["standalone_replay_report"]["fingerprint"] != now["standalone_replay_report"]["fingerprint"]:
                    raise V104Error("V104_EXISTING_ARCHIVED_REPLAY_RESULT_CHANGED")
            outcomes[now["standalone_replay_report"]["status"]]+=1
            counts["original_signal_pairs_verified"]+=1
        by_month[month]={"signal_count":len(older),
                         "newly_registered_original_2026_sources":source_changed,
                         "refreshed_original_V55_outcomes":dict(sorted(outcomes.items())),
                         "original_V65_sha":original["fingerprint"],
                         "refreshed_V65_sha":changed["fingerprint"]}
        all_source_shas.append(changed["fingerprint"])
    if (counts["original_signal_pairs_verified"]!=227
            or refreshed_summary["exchange_sessions"]!=230
            or len({x["query_id"] for x in qids_changed})!=len(qids_changed)):
        raise V104Error("V104_COMPARISON_GRID_CHANGED")
    return write_once(output,{
        "contract":CONTRACT+"-source-recovery-frozen-signal-compare-v1",
        "original_v103_sha":original_summary["fingerprint"],
        "original_v103_zip_sha":zip_sha,
        "refreshed_v103_sha":refreshed_summary["fingerprint"],
        "original_signal_pairs_verified":counts["original_signal_pairs_verified"],
        "newly_registered_original_2026_sources":len(qids_changed),
        "per_month":by_month,
        "source_state_changes":qids_changed,
        "refreshed_original_v65_month_shas":all_source_shas,
        "refreshed_contiguous_account_known":refreshed_summary["continuous_cash_known"],
        "refreshed_contiguous_quote_pnl_if_qualified":
            refreshed_summary["total_contiguous_quote_pnl_if_qualified"],
        "no_original_entry_signal_or_exit_policy_changed":True,
        "all_unpriced_original_exits_still_censored":True,
        "no_broker_orders":True,
        "original_master_holdout_2026_may_aug_unopened":True,
    })


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-v103-full-zip",type=Path,required=True)
    p.add_argument("--refreshed-v103-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=compare(args.original_v103_full_zip,args.refreshed_v103_dir,args.output)
        print(f"V104 VERIFIED unchanged_signals={result['original_signal_pairs_verified']} "
              f"newly_registered={result['newly_registered_original_2026_sources']} "
              "broker_orders=0 historical_alpha_proven=False")
        return 0
    except (ValueError,OSError,TypeError,KeyError,RuntimeError) as exc:
        print(f"V104 COMPARE STOP error={type(exc).__name__}: {str(exc)[:180]}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
