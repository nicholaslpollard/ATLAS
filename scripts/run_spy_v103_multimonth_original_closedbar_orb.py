from __future__ import annotations

"""V103 full multi-month, OFFLINE original V55/V65 closed-bar ORB experiment.

No option-provider SDK/session creation, no query dispatch or broker requests.
One full SHA audit per existing monthly SPY native minute unit; V65 source
and V55 exit rules stay unchanged. Missing stock/option sources are CENSORED.
"""
import argparse
from collections import Counter
from datetime import date, timedelta, datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE, discover_minute_units,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v103_offline_orb_causal_account import (
    START, V65, V103Error, classify, chain_months, signed, verify,
)
from scripts.run_spy_v65_full_june_offline_simulator_readiness import inspect

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v103-multimonth-existing-v55-v65-original-orb-source-census-v1"
FIRST = date(2018, 1, 1)


def month_bounds(start, end):
    if (start > end or start < FIRST or end > B34_MAX_SAMPLE_DATE
            or (end-start).days > 3660):
        raise V103Error("V103_UNSUPPORTED_OR_PROTECTED_DATE_RANGE")
    cursor = start.replace(day=1)
    while cursor <= end:
        nextmonth = (cursor.replace(day=28)+timedelta(days=4)).replace(day=1)
        left, right = max(start,cursor), min(end,nextmonth-timedelta(days=1))
        yield left, right
        cursor = nextmonth


def original_gzip_once(raw_path, archive_path):
    """Losslessly retain original signed V65 JSON; raw bytes verified before delete."""
    if not raw_path.is_file() or raw_path.is_symlink():
        raise V103Error("V103_ORIGINAL_MONTH_REPORT_MISSING")
    digest = hashlib.sha256()
    bytes_count = 0
    with raw_path.open("rb") as stream, archive_path.open("xb") as dest:
        with gzip.GzipFile(fileobj=dest, mode="wb", compresslevel=6, mtime=0) as gz:
            for chunk in iter(lambda: stream.read(1024*1024), b""):
                digest.update(chunk)
                bytes_count += len(chunk)
                gz.write(chunk)
        dest.flush()
        os.fsync(dest.fileno())
    checked = hashlib.sha256()
    with gzip.open(archive_path, "rb") as verify_stream:
        for chunk in iter(lambda: verify_stream.read(1024*1024), b""):
            checked.update(chunk)
    if checked.hexdigest() != digest.hexdigest():
        raise V103Error("V103_LOSSLESS_GZIP_ORIGINAL_SHA_MISMATCH")
    zipped_sha = hashlib.sha256()
    with archive_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            zipped_sha.update(chunk)
    raw_path.unlink()
    return {"path": archive_path.name, "raw_sha256": digest.hexdigest(),
            "raw_bytes": bytes_count, "gzip_sha256": zipped_sha.hexdigest(),
            "compressed_bytes": archive_path.stat().st_size, "source_preserved": True}


def save_signed(path, record):
    if path.exists() or path.is_symlink():
        raise V103Error("V103_IMMUTABLE_ARTIFACT_EXISTS")
    result = signed(record)
    with path.open("x", encoding="utf8") as f:
        json.dump(result, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return result


def frozen_calendar(start, end, *, cal=None):
    cal = cal or get_market_calendar()
    sessions = cal.sessions_in_range(start,end)
    standard, short = [], []
    for day in sessions:
        _, close = cal.regular_open_close(day)
        local = close.astimezone(ET)
        if local.hour < 15 or (local.hour == 15 and local.minute < 30):
            short.append(day)
        else:
            standard.append(day)
    return sessions, standard, short


def run(out_dir, *, start=date(2025, 6, 1), end=date(2026, 4, 30),
        discover=discover_minute_units, inspector=inspect,
        calendar_factory=get_market_calendar, announce=print):
    windows = list(month_bounds(start,end))
    if out_dir.exists() or out_dir.is_symlink() or len(windows)>120:
        raise V103Error("V103_OUTPUT_OR_MONTH_BOUNDARY_INVALID")
    out_dir.mkdir(parents=True, exist_ok=False)
    month_dir = out_dir/"months"
    month_dir.mkdir()
    calendar = calendar_factory()
    all_sessions, _, _ = frozen_calendar(start,end,cal=calendar)
    if not all_sessions:
        raise V103Error("V103_ZERO_VALID_EXCHANGE_SESSIONS")
    layout = V2Layout.beneath(ROOT/"data")
    compact_months = []
    receipts = []
    monthly_results = []
    for lo,hi in windows:
        label = f"{lo.year:04d}-{lo.month:02d}"
        announce(f"V103 MONTH_START month={label} dates={lo}/{hi} broker_orders=0 provider_calls=0")
        month_sessions, standard, short = frozen_calendar(lo,hi,cal=calendar)
        if not month_sessions:
            continue
        folder = layout.checkpoints/"native_units"/"1m"/f"year={lo.year:04d}"/f"month={lo.month:02d}"
        month_status = "ORIGINAL_MONTH_AVAILABLE"
        units = []
        if not folder.is_dir() or folder.is_symlink():
            month_status = "NATIVE_MONTH_CHECKPOINT_NOT_PRESENT"
        else:
            available = discover(layout,target_year=lo.year,target_month=lo.month,progress=None)
            units = [u for u in available if u.year==lo.year
                     and u.month==lo.month and "SPY" in u.symbols]
            if len(units)==0:
                month_status = "NO_SPY_ORIGINAL_CHECKPOINT"
            if len(units)>1:
                raise V103Error("V103_AMBIGUOUS_ORIGINAL_SPY_MONTH")
        compact = {"month": label, "start":lo.isoformat(),"end":hi.isoformat(),
                   "status":month_status,"excluded_early_closes":short,
                   "classified_sessions":None,"original_v65_sha":None}
        if month_status == "ORIGINAL_MONTH_AVAILABLE" and standard:
            raw = month_dir/f"v65_original_{lo.year:04d}{lo.month:02d}.json"
            original = inspector(lo,hi,raw,
                session_calendar=lambda _a,_b: standard,
                progress=announce)
            if not verify(original) or original.get("contract")!=V65:
                raise V103Error("V103_ORIGINAL_V65_REPORT_SHA_INVALID")
            if (len(original["session_reports"])!=len(standard)
                    or {x["session"] for x in original["session_reports"]}
                       != {d.isoformat() for d in standard}
                    or original["provider_requests"] != 0
                    or original["broker_orders"] != 0):
                raise V103Error("V103_V65_SESSION_OR_PROVIDER_DRIFT")
            compact["classified_sessions"] = []
            for row in original["session_reports"]:
                day = date.fromisoformat(row["session"])
                verdict, details = classify(row, day)
                compact["classified_sessions"].append(signed({
                    "session":day.isoformat(),
                    "disposition":verdict,"detail":details,
                    "original_v65_session_sha":row["fingerprint"],
                    "compact_v103_disposition":True,
                }))
            compact["original_v65_sha"] = original["fingerprint"]
            receipt = original_gzip_once(
                raw, month_dir/f"v65_original_{lo.year:04d}{lo.month:02d}.json.gz")
            receipts.append({"month":label, **receipt, "original_v65_sha":original["fingerprint"]})
            del original
        elif month_status == "ORIGINAL_MONTH_AVAILABLE":
            compact["classified_sessions"] = []
            compact["original_v65_sha"] = None
        # Do not write the huge duplicated V65 journals into the compact ledger.
        eligible = [x for x in month_sessions if x not in short]
        standalone = chain_months([compact],calendar_sessions=month_sessions,initial=START)
        saved = save_signed(month_dir/f"v103_account_{lo.year:04d}{lo.month:02d}.json",{
            "contract":CONTRACT+"-single-month-standalone-account-v1",
            "month":label,"sessions":len(month_sessions),
            "standard_sessions":len(eligible),
            "original_v65_sha":compact["original_v65_sha"],
            "account":standalone,
            "provider_requests":0,"broker_orders":0,
            "not_compounded_with_other_months":True,
        })
        monthly_results.append({
            "month":label, "account_sha":standalone["fingerprint"],
            "report_sha":saved["fingerprint"],
            "source_status":month_status,"session_count":len(month_sessions),
            "closed_trades_if_prefix_known":standalone["pre_censor_flat_closes"],
            "terminal_cash_if_complete":standalone["terminal_equity_if_source_complete_usd"],
            "first_source_censor":standalone["first_account_censor"],
            "dispositions":standalone["dispositions"],
        })
        compact_months.append(compact)
        announce(f"V103 MONTH_DONE month={label} source={month_status} "
                 f"cash_complete={not standalone['first_account_censor']} "
                 f"closed_prior_to_censor={standalone['pre_censor_flat_closes']} "
                 "provider_calls=0 broker_orders=0")
    if not compact_months:
        raise V103Error("V103_NO_MONTH_RESEARCH_OUTPUT")
    combined = chain_months(compact_months,calendar_sessions=all_sessions,initial=START)
    saved_account = save_signed(out_dir/"chronological_account.json",{
        "contract":CONTRACT+"-full-contiguous-account-v1",
        "account":combined, "not_a_true_broker_fill":True,
        "sources_not_filled_with_zero_profit":True,
        "protected_master_holdout_read":False,
        "provider_requests":0,"broker_orders":0,
    })
    summary = save_signed(out_dir/"summary.json",{
        "contract":CONTRACT,
        "window_start":start.isoformat(),"window_end":end.isoformat(),
        "months":len(compact_months),
        "exchange_sessions":len(all_sessions),
        "original_V65_gzip_receipts":receipts,
        "monthly_source_linked_accounts":monthly_results,
        "combined_account_sha":saved_account["fingerprint"],
        "continuous_cash_known":combined["first_account_censor"] is None,
        "total_contiguous_quote_pnl_if_qualified":combined["cash_pnl_if_entire_window_complete_usd"],
        "first_contiguous_account_censor":combined["first_account_censor"],
        "monthly_cash_is_not_assumed_to_be_combined_profits":True,
        "native_1m_end_of_bar_publication_assumed_not_first_delivery_proven":True,
        "original_strategy_is_V55_not_V51_first_tick":True,
        "zero_option_provider_calls":True,"zero_broker_orders":True,
        "no_master_holdout_access":True,
        "profitable_strategy_proven":False,
    })
    announce(f"V103 COMPLETE months={len(compact_months)} "
             f"continuous_cash_known={summary['continuous_cash_known']} "
             f"monthly_reports={len(monthly_results)} "
             "provider_calls=0 broker_orders=0")
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",type=date.fromisoformat,default=date(2025,6,1))
    p.add_argument("--end",type=date.fromisoformat,default=date(2026,4,30))
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.output_dir,start=args.start,end=args.end)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"V103 STOP {type(exc).__name__}: {str(exc)[:200]} "
              "new_provider_calls=0 broker_orders=0",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
