from __future__ import annotations

"""Read-only preview of first possible SPY 0DTE ORB minutes from native V2 SIP.

A provider one-minute bar can be shown as a candidate, but neither the minute
high/low nor historical timestamp constitutes an independently known first
breakout tick, selected option strike, or executable trade.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import time as _time
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE, IntradaySemanticsAuditError,
    _sample_rows, discover_minute_units, verify_unit_integrity,
    validate_minute_rows,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-spy-native-minute-five-minute-orb-inventory-v51"
ET=ZoneInfo("America/New_York")


def _verify_monthly_unit_with_progress(unit, emit: Callable[[str], None] | None) -> dict:
    """Stream and verify BOTH pinned source hashes; report true byte milestones.

    Hashing is mandatory, not skipped or reduced to speed the demonstration.
    The source is an entire native monthly unit, potentially many gigabytes.
    """
    if emit is None:
        return verify_unit_integrity(unit)
    sources=(
        ("canonical",unit.canonical_path,unit.canonical_sha256),
        ("raw_bundle",unit.raw_bundle_path,unit.raw_bundle_sha256),
    )
    errors=[]
    readable=[]
    for label,path,expected in sources:
        if path.is_symlink() or not path.is_file():
            errors.append(f"{label} missing or linked: {path}")
            continue
        readable.append((label,path,expected,path.stat().st_size))
    total_bytes=sum(size for _,_,_,size in readable)
    cumulative=0
    milestone=10
    started=_time.monotonic()
    emit("STAGE_START original monthly SHA verification"
         f" unit={unit.unit_id} files={len(readable)}/2"
         f" total_bytes={total_bytes} provider_requests=0")
    for label,path,expected,size in readable:
        emit(f"SOURCE_START label={label} filename={path.name} size_bytes={size}")
        digest=hashlib.sha256()
        # Chunked stream bounds RAM and makes percentage updates reflect
        # actual checked bytes, not guessed provider progress.
        read_size=max(1,min(4*1024*1024,total_bytes//100 if total_bytes else 1))
        with path.open("rb") as inp:
            while True:
                chunk=inp.read(read_size)
                if not chunk:
                    break
                digest.update(chunk)
                cumulative+=len(chunk)
                elapsed=max(_time.monotonic()-started,0.001)
                while total_bytes and cumulative*100>=total_bytes*milestone and milestone<=100:
                    rate=cumulative/elapsed
                    eta=(total_bytes-cumulative)/rate if rate>0 else None
                    emit(f"PROGRESS_{milestone}PCT phase=verify_full_original_SHA"
                         f" completed_bytes={cumulative}/{total_bytes}"
                         f" percent={100*cumulative/total_bytes:.1f}"
                         f" current_source={label}:{path.name}"
                         f" elapsed={elapsed:.1f}s throughput_mib_s={rate/(1024**2):.2f}"
                         f" eta_rough_s={eta:.1f}" if eta is not None else
                         f"PROGRESS_{milestone}PCT phase=verify_full_original_SHA"
                         f" completed_bytes={cumulative}/{total_bytes}"
                         f" percent={100*cumulative/total_bytes:.1f} eta_rough=unknown")
                    milestone+=10
        observed=digest.hexdigest()
        if not expected:
            errors.append(f"{label} checkpoint has no sha256")
        elif observed!=expected:
            errors.append(f"{label} sha256 mismatch")
        emit(f"SOURCE_{'VERIFIED' if expected and observed==expected else 'REJECTED'}"
             f" label={label} bytes={size} elapsed={_time.monotonic()-started:.1f}s")
    emit(f"STAGE_{'PASS' if not errors else 'FAIL'} original_full_sha"
         f" files={len(readable)}/2 completed_bytes={cumulative}/{total_bytes}"
         f" elapsed={_time.monotonic()-started:.1f}s provider_requests=0")
    return {
        "checkpoint_path":str(unit.checkpoint_path),
        "unit_id":unit.unit_id,"status":unit.status,
        "canonical_path":str(unit.canonical_path),
        "raw_bundle_path":str(unit.raw_bundle_path),
        "accepted":not errors,"errors":errors,
    }


def _price(value):
    try:
        val=Decimal(str(value))
    except (TypeError,InvalidOperation,ValueError) as exc:
        raise ValueError("V51_NATIVE_SPY_BAR_PRICE_INVALID") from exc
    if not val.is_finite() or val<=0:
        raise ValueError("V51_NATIVE_SPY_BAR_PRICE_INVALID")
    return val


def preview(rows: list[dict], *, session: date, source_sha256: str,
            source_unit_id: str) -> dict:
    by_start={}
    for row in rows:
        stamp=row["timestamp_utc"]
        if isinstance(stamp,str):
            stamp=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if not isinstance(stamp,datetime) or stamp.utcoffset() is None:
            raise ValueError("V51_NATIVE_SPY_TIMESTAMP_NOT_AWARE")
        local=stamp.astimezone(ET)
        if local.date()!=session or row.get("symbol")!="SPY":
            raise ValueError("V51_NATIVE_SPY_SESSION_MISMATCH")
        if local in by_start:
            raise ValueError("V51_NATIVE_SPY_DUPLICATE_MINUTE")
        op,hi,lo,cl=(_price(row[k]) for k in ("open","high","low","close"))
        if not lo<=min(op,cl)<=max(op,cl)<=hi:
            raise ValueError("V51_NATIVE_SPY_BAD_BAR_GEOMETRY")
        by_start[local]=(op,hi,lo,cl)
    open_clock=datetime.combine(session,time(9,30),tzinfo=ET)
    opening=[by_start.get(open_clock+timedelta(minutes=i)) for i in range(5)]
    raw_available=all(x is not None for x in opening)
    first=None
    missing=0
    hi=lo=None
    if raw_available:
        hi=max(x[1] for x in opening)
        lo=min(x[2] for x in opening)
        for minute in range(5,360):
            at=open_clock+timedelta(minutes=minute)
            sample=by_start.get(at)
            if sample is None:
                missing+=1
                break  # absence before breakout censors causal first event
            above=sample[1]>hi
            below=sample[2]<lo
            if above or below:
                first={"minute_start_et":at.isoformat(),
                       "minute_close_available_no_earlier_than_et":(at+timedelta(minutes=1)).isoformat(),
                       "direction_possible":"BOTH_AMBIGUOUS" if above and below else "CALL" if above else "PUT",
                       "high":str(sample[1]),"low":str(sample[2])}
                break
    reasons=[]
    if not raw_available:
        reasons.append("FIVE_OPENING_SPY_MINUTES_NOT_ALL_IN_NATIVE_SOURCE")
    if missing:
        reasons.append("MISSING_MINUTE_BEFORE_FIRST_POSSIBLE_BREAKOUT")
    if first and first["direction_possible"]=="BOTH_AMBIGUOUS":
        reasons.append("BOTH_BREAKOUT_DIRECTIONS_IN_FIRST_CANDIDATE_MINUTE")
    if not first and not reasons:
        reasons.append("NO_BREAKOUT_IN_AVAILABLE_09_35_TO_15_30_SOURCE")
    reasons.append("FIRST_BREAKOUT_TICK_AND_PUBLICATION_CLOCK_NOT_PROVEN")
    report={
        "contract":CONTRACT,"status":"OFFLINE_SOURCE_ONLY_PREVIEW_NOT_HISTORICAL_TRADE",
        "session":session.isoformat(),"symbol":"SPY",
        "source_unit_id":source_unit_id,"canonical_original_source_sha256":source_sha256,
        "observed_native_minute_rows":len(rows),
        "opening_range_completely_observed":raw_available,
        "opening_high":str(hi) if hi is not None else None,
        "opening_low":str(lo) if lo is not None else None,
        "first_possible_breakout_minute":first,
        "source_reason_codes":reasons,
        "historical_pit_publication_proven":False,
        "historical_option_contract_selected":False,
        "broker_fills":0,"provider_calls":0,"strategy_pnl":None,
    }
    report["fingerprint"]=_fingerprint(report)
    return report


def inspect_native_spy_day(project_root: Path, *, session: date,\n                           progress: Callable[[str], None] | None = None) -> dict:
    if session>B34_MAX_SAMPLE_DATE:
        raise ValueError("V51_REFUSES_UNINSPECTED_MASTER_OR_FUTURE_SOURCE_DATE")
    layout=V2Layout.beneath(project_root/"data")
    if progress:\n        progress(f"STAGE_START discover_native_minutes date={session.isoformat()} provider_requests=0")
    try:
        units=discover_minute_units(layout)
    except IntradaySemanticsAuditError:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"NO_COMPLETED_NATIVE_MINUTE_CHECKPOINTS",
                "source_ready":False,"provider_calls":0}
    if progress:\n        progress(f"STAGE_PASS discover_native_minutes scanned_units={len(units)}")
    matching=[u for u in units if (u.year,u.month)==(session.year,session.month)
              and "SPY" in u.symbols]
    if not matching:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"NO_SPY_NATIVE_MINUTE_MONTHLY_SOURCE",
                "source_ready":False,"provider_calls":0}
    if len(matching)!=1:
        raise ValueError("V51_AMBIGUOUS_SPY_MONTHLY_SOURCE_UNITS")
    unit=matching[0]
    integrity=_verify_monthly_unit_with_progress(unit,progress)
    if not integrity["accepted"]:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"CANONICAL_SOURCE_SHA_OR_RAW_BUNDLE_REJECTED",
                "unit_id":unit.unit_id,"source_ready":False,
                "integrity_errors":integrity["errors"],"provider_calls":0}
    if progress:\n        progress(f"STAGE_START read_SPY_one_session_from_monthly_parquet date={session.isoformat()} file={unit.canonical_path.name}")
    rows=_sample_rows(unit.canonical_path,symbol="SPY",session_date=session)
    if progress:\n        progress(f"STAGE_PASS read_SPY_one_session_from_monthly_parquet rows={len(rows)}")
    if not rows:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"NO_SPY_MINUTES_ON_REQUESTED_DATE",
                "source_ready":False,"provider_calls":0}
    if progress:\n        progress(f"STAGE_START validate_SPY_1m_geometry rows={len(rows)}")
    check=validate_minute_rows(rows,sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
        symbol="SPY",session_date=session)
    if not check["accepted"]:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"SPY_CANONICAL_MINUTE_GEOMETRY_UNQUALIFIED",
                "source_ready":False,"source_row_errors":check["errors"][:15],
                "provider_calls":0}
    if progress:\n        progress("STAGE_PASS validate_SPY_1m_geometry")
        progress("STAGE_START classify_first_possible_breakout_minute")
    result=preview(rows,session=session,source_sha256=unit.canonical_sha256,
                   source_unit_id=unit.unit_id)
    if progress:\n        progress("STAGE_PASS classify_first_possible_breakout_minute")
    result["source_ready"]=True
    result["integrity_validated"]=True
    result["minute_source_warning_codes"]=check["warnings"]
    result["fingerprint"]=_fingerprint({k:v for k,v in result.items() if k!="fingerprint"})
    return result
